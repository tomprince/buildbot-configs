import re

from buildbot.status.results import SUCCESS, FAILURE, WARNINGS
from buildbot.process.buildstep import LogLineObserver
from buildbot.steps.shell import ShellCommand

class NotmuchTestObserver(LogLineObserver):
    test_line_re = re.compile(' ([A-Z]*) *(.*)')
    output_line_re = re.compile('\t(.*)')
    test_group_line_re = re.compile('([a-z-]*): *(.*)')
    summary_line_re = re.compile(r'Notmuch test suite complete\.')

    def __init__(self, problems, **kwargs):
        LogLineObserver.__init__(self, **kwargs)
        self.problems = problems
	self.results = {
			'total': 0,
			'broken': 0,
			'fixed': 0,
			'skipped': 0,
			'failed': 0,
			'passed': 0,
			}
	self.numTests = 0
	self.finished = False
	self.current_header = None


    def outLineReceived(self, line):
        if self.finished:
            self.processSummaryLine(line)
            return

        m = self.summary_line_re.match(line)
        if m:
            self.finished = True
            return

        m = self.test_group_line_re.match(line)
        if m:
            self.current_header = line
            self.current_group = m.group(1)
            return

        m = self.test_line_re.match(line)
        if m:
            self.numTests += 1
            self.step.setProgress('tests', self.numTests)
            
            result = m.group(1)
            if result == 'BROKEN' or result == 'FAIL':
                if self.current_header:
                    self.problems.addStdout("%s\n" % self.current_header)
                    self.current_header = None
                self.problems.addStdout("%s\n" % line)
            return

        m = self.output_line_re.match(line)
        if m:
            if self.current_header:
                self.problems.addStdout("%s\n" % self.current_header)
                self.current_header = None
            self.problems.addStdout("%s\n" % line)

    def processSummaryLine(self, line):
        m = re.match(r'All (\d+) tests? passed\.', line)
        if m:
            self.results['passed'] = self.results['total'] = int(m.group(1))
	    return
        m = re.match(r'All (\d+) tests? behaved as expected \((\d+) expected failures?\)\.', line)
        if m:
            self.results['total'] = int(m.group(1))
            self.results['broken'] = int(m.group(2))
            self.results['passed'] = self.results['total'] - self.results['broken']
	    return
        m = re.match(r'(\d+)/(\d+) tests passed\.', line)
        if m:
            self.results['passed'] = int(m.group(1))
            self.results['total'] = int(m.group(2))
	    return
        m = re.match(r'(\d+) broken tests? failed as expected\.', line)
        if m:
            self.results['broken'] = int(m.group(1))
	    return
        m = re.match(r'(\d+) broken tests? now fixed\.', line)
        if m:
            self.results['fixed'] = int(m.group(1))
	    return
        m = re.match(r'(\d+) tests? failed\.', line)
        if m:
            self.results['failed'] = int(m.group(1))
	    return
        m = re.match(r'(\d+) tests? skipped\.', line)
        if m:
            self.results['skipped'] = int(m.group(1))
	    return

class NotmuchTest(ShellCommand):
    name = "tests"
    
    progressMetrics = ('output', 'tests')

    flunkOnFailure = True
    
    def __init__(self, emacs = None, **kwargs):
        ShellCommand.__init__(self, **kwargs)
        self.addFactoryArguments(emacs=emacs)

	command=['make', 'test']
	if emacs:
		command += [ 'TEST_EMACS=' + emacs ]
	self.setCommand(command)
	
    def setupLogfiles(self, cmd, logfiles):
        problems = self.addLog("problems")
        self.logobserver = NotmuchTestObserver(problems)
        self.addLogObserver('stdio', self.logobserver)
	ShellCommand.setupLogfiles(self, cmd, logfiles)
        
    def commandComplete(self, cmd):
        counts = self.logobserver.results

        text = []

        text.append("tests")
        if counts['failed']:
            results = FAILURE
            text.append("%d failed" % counts['failed'])
        else:
            results = SUCCESS
            text.append("%d passed" % counts['passed'])

        if counts['skipped']:
            text.append("%d skipped" %  counts['skipped'])
        if counts['broken']:
            text.append("%d broken" %  counts['broken'])

        if counts['fixed']:
            text.append("%d fixed" % counts['fixed'])
            if results == SUCCESS:
                results = WARNINGS

        self.results = results
        self.text = text

    def evaluateCommand(self, cmd):
        return self.results

    def getText(self, cmd, results):
        return self.text

