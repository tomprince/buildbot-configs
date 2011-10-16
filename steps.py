from buildbot.process.buildstep import LoggedRemoteCommand
from buildbot.interfaces import BuildSlaveTooOldError
import stat

def FileExists(step, filename):
	slavever = step.slaveVersion('stat')
	if not slavever:
		raise BuildSlaveTooOldError("slave is too old, does not know "
				"about stat")

	def commandComplete(cmd):
		if cmd.rc != 0:
			return False
		s = cmd.updates["stat"][-1]
		if stat.S_ISREG(s[stat.ST_MODE]):
			return True
		else:
			return False

	cmd = LoggedRemoteCommand('stat', {'file': filename })
	d = step.runCommand(cmd)
	d.addCallback(lambda res: commandComplete(cmd))
	return d
