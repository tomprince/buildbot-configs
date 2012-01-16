
import os

from twisted.application import service
from buildslave.bot import BuildSlave
from buildbot.master import BuildMaster

basedir = r'/Depot/BuildBot/master/test'
rotateLength = 10000000
maxRotatedFiles = 1

# if this is a relocatable tac file, get the directory containing the TAC
if basedir == '.':
    import os.path
    basedir = os.path.abspath(os.path.dirname(__file__))

# note: this line is matched against to check that this is a buildslave
# directory; do not edit it.
application = service.Application('buildmaster')

try:
  from twisted.python.logfile import LogFile
  from twisted.python.log import ILogObserver, FileLogObserver
  logfile = LogFile.fromFullPath(os.path.join(basedir, "twistd.log"), rotateLength=rotateLength,
                                 maxRotatedFiles=maxRotatedFiles)
  application.setComponent(ILogObserver, FileLogObserver(logfile).emit)
except ImportError:
  # probably not yet twisted 8.2.0 and beyond, can't set log yet
  pass


configfile = r'master.cfg'

m = BuildMaster(basedir, configfile)
m.setServiceParent(application)
m.log_rotation.rotateLength = rotateLength
m.log_rotation.maxRotatedFiles = maxRotatedFiles

buildmaster_host = 'master-socket'
port = 9000
slavename = 'slave'
passwd = 'slave'
keepalive = 600
usepty = 0
umask = None
maxdelay = 300

s = BuildSlave(buildmaster_host, port, slavename, passwd, basedir,
               keepalive, usepty, umask=umask, maxdelay=maxdelay)
s.setServiceParent(application)

