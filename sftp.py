import os

from twisted.spread import pb
from twisted.python import log, failure
from buildbot.process.buildstep import LoggedRemoteCommand, BuildStep
from buildbot.process.buildstep import SUCCESS, FAILURE, SKIPPED
from buildbot.interfaces import BuildSlaveTooOldError


from twisted.internet import defer

from twisted.conch.ssh.common import NS
from twisted.conch.scripts.cftp import ClientOptions
from twisted.conch.ssh.filetransfer import FileTransferClient
from twisted.conch.ssh import filetransfer
from twisted.conch.client.connect import connect
from twisted.conch.ssh.connection import SSHConnection
from twisted.conch.ssh.channel import SSHChannel
from twisted.conch.ssh import keys
from twisted.conch.client.knownhosts import KnownHostsFile



from twisted.conch.ssh import userauth

class SSHUserAuthClient(userauth.SSHUserAuthClient):
    def __init__(self, user, options, *args):
        userauth.SSHUserAuthClient.__init__(self, user, *args)
        self.options = options
        self._tried_key = None

    def getPublicKey(self):
        try:
            if self._tried_key:
                return
            file = self.options['identity']
            if not os.path.exists(file):
                log.msg("here3 %s" % file)
                return None
            key = keys.Key.fromFile(file)
            self._tried_key = key
            return key
        except keys.BadKeyError:
            return None
        except keys.EncryptedKeyError:
            return None
        except:
            log.err(failure.Failure(), "failed to get public key")
    def getPrivateKey(self):
        return defer.succeed(self._tried_key)

def verifyHostKey(transport, host, pubKey, fingerprint):
    known_hosts = transport.factory.options['known-hosts']
    if not known_hosts:
        return defer.succeed(True)

    actualHost = transport.factory.options['host']
    actualKey = keys.Key.fromString(pubKey)
    kh = KnownHostsFile.fromPath(known_hosts)
    return (kh.hasHostKey(host, actualKey) or
        kh.hasHostKey(actualHost, actualKey))


class SFTPSession(SSHChannel):
    name = 'session'

    def channelOpen(self, whatever):
        d = self.conn.sendRequest(
                self, 'subsystem', NS('sftp'), wantReply=True)
        d.addCallbacks(self._cbSFTP)


    def _cbSFTP(self, result):
        client = FileTransferClient()
        client.makeConnection(self)
        self.dataReceived = client.dataReceived
        self.conn._sftp.callback(client)

class SFTPConnection(SSHConnection):
    def serviceStarted(self):
        self.openChannel(SFTPSession())
    def channelClosed(self, channel):
        SSHConnection.channelClosed(self, channel)
        self.transport.transport.loseConnection()

def sftp(user, host, port, privkey, known_hosts):
    options = ClientOptions()
    options['host'] = host
    options['port'] = port
    options['identity'] = privkey
    options['known-hosts'] = known_hosts
    conn = SFTPConnection()
    conn._sftp = defer.Deferred()
    auth = SSHUserAuthClient(user, options, conn)
    connect(host, port, options, verifyHostKey, auth)
    return conn._sftp

class _FileWriter(pb.Referenceable):
    """
    Helper class that acts as a file-object with write access
    """

    def __init__(self, destfile):
        # Create missing directories.
        self.queue = destfile
        self.offset = 0

    def _write(self, destfile, data, cb):
        offset = self.offset
        d = destfile.writeChunk(offset, data)
        self.offset += len(data)
        d.addCallbacks(cb.callback, cb.errback)
        return destfile

    def remote_write(self, data):
        """
        Called from remote slave to write L{data} to L{fp} within boundaries
        of L{maxsize}

        @type  data: C{string}
        @param data: String of data to write
        """
        d = defer.Deferred()
        self.queue.addCallback(self._write, data, d)
        return d

    def remote_utime(self, accessed_modified):
        pass

    def remote_close(self, *args):
	pass

    def close(self):
        """
        Called by remote slave to state that no more data will be transfered
        """
        @self.queue.addCallback
        def close(f):
            f.close()
            return f

class SFTPUploadPassthrough(BuildStep):
    """
    Base class for FileUpload and FileDownload to factor out common
    functionality.
    """
    renderables = [ 'workdir', 'slavesrc', 'remotedest', 'url' ]

    haltOnFailure = True
    flunkOnFailure = True

    def setDefaultWorkdir(self, workdir):
        if self.workdir is None:
            self.workdir = workdir

    def interrupt(self, reason):
        self.addCompleteLog('interrupt', str(reason))
        if self.cmd:
            d = self.cmd.interrupt(reason)
            return d

    def finished(self, result):
        # Subclasses may choose to skip a transfer. In those cases, self.cmd
        # will be None, and we should just let BuildStep.finished() handle
        # the rest
        if result == SKIPPED:
            return BuildStep.finished(self, SKIPPED)
        #if self.cmd.stderr != '':
        #    self.addCompleteLog('stderr', self.cmd.stderr)

        if self.cmd.rc is None or self.cmd.rc == 0:
            return BuildStep.finished(self, SUCCESS)
        return BuildStep.finished(self, FAILURE)


    name = 'upload'


    def __init__(self, slavesrc, remotedest, user, host, key,
                 port=22,
                 workdir=None, url=None,
		 known_hosts=None,
                 **buildstep_kwargs):
        BuildStep.__init__(self, **buildstep_kwargs)
        self.addFactoryArguments(slavesrc=slavesrc,
                                 remotedest=remotedest,
                                 workdir=workdir,
                                 user=user,
                                 host=host,
                                 port=port,
                                 key=key,
                                 url=url,
				 known_hosts=known_hosts,
                                 )

        self.slavesrc = slavesrc
        self.remotedest = remotedest
        self.workdir = workdir
        self.user = user
        self.host = host
        self.port = port
        self.key = key
        self.url = url
	self.known_hosts = known_hosts
        assert os.path.exists(key), "missing ssh-key"

    def start(self):
        version = self.slaveVersion("uploadFile")

        if not version:
            m = "slave is too old, does not know about uploadFile"
            raise BuildSlaveTooOldError(m)

        log.msg("FileUpload started, from slave %r to remote %r@%r:%r"
                % (self.slavesrc, self.user, self.host, self.remotedest))

        self.step_status.setText(['uploading', os.path.basename(self.slavesrc)])
        if self.url is not None:
            self.addURL(os.path.basename(self.remotedest), self.url)

        d = sftp(self.user, self.host, self.port, self.key, self.known_hosts)
        @d.addCallback
        def _gotSFTPConnection(sftp):
            self._sftp_conn = sftp
            return sftp.openFile(self.remotedest, filetransfer.FXF_WRITE | filetransfer.FXF_TRUNC | filetransfer.FXF_CREAT, {})
        self._fw = _FileWriter(d)

        # default arguments
        args = {
            'slavesrc': self.slavesrc,
            'workdir': self.workdir,
            'writer': self._fw,
            'maxsize': None,
            'blocksize': 16*1024,
            'keepstamp': False,
            }

        self.cmd = LoggedRemoteCommand('uploadFile', args)
        d = self.runCommand(self.cmd)
        d.addBoth(self._closeSFTPConnection)
        d.addCallback(self.finished).addErrback(self.failed)

    def _closeSFTPConnection(self, res):
        self._fw.queue.addBoth(lambda _:
                self._sftp_conn.transport.loseConnection())
        self._fw.queue.addCallback(lambda _: res)
        return self._fw.queue
