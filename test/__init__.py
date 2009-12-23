import sys
import codecs
import doctest
import unittest
import functools
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import werkzeug

def find_all_modules(packages):
    for package in packages:
        yield package
        try:
            for module in werkzeug.find_modules(package, include_packages=True,
                                                recursive=True):
                yield module
        except ValueError, e:
            if e.args != ("'%s' is not a package" % package,):
                raise
        except ImportError:
            # Maybe this is not a module
            # (eg an unittest class or method)
            pass
def get_tests(packages):
    """
    Return a TestSuite
    """
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for module_name in find_all_modules(packages):
        suite.addTests(loader.loadTestsFromName(module_name))
        try:
            tests = doctest.DocTestSuite(module_name)
        except ValueError, e:
            # doctest.DocTestSuite throws ValueError when there is no test
            if len(e.args) != 2 or e.args[1] != "has no tests":
                raise
        except ImportError:
            # unitest's loadTestsFromName worked. Maybe this is not a module
            # (eg an unittest class or method)
            pass
        else:
            suite.addTests(tests)
    return suite

def find_TODOs(packages):
    for module_name in find_all_modules(packages):
        if module_name == __name__:
            # prevent this script from finding itself
            continue
        filename = werkzeug.import_string(module_name).__file__
        if filename[-4:] in ('.pyc', '.pyo'):
            filename = filename[:-1]
        f = open(filename)
        todo_lines = []
        todo_count = 0
        for line_no, line in enumerate(f):
            count = line.count('TODO')
            if count:
                todo_count += count
                todo_lines.append(line_no + 1) # enumerate starts at 0
        f.close()
        if todo_count:
            yield filename, todo_count, todo_lines

def print_TODOs(packages):
    todos = list(find_TODOs(packages))
    if not todos:
        return # max() of an empty list raises an exception
    width = max(len(module) for module, count, lines in todos)
    for module, count, lines in todos:
        print '%-*s' % (width, module), ':', count,
        if count > 1:
            print 'TODOs on lines',
        else:
            print 'TODO  on line ',
        print ', '.join(str(line) for line in lines)

class FakeStdout(object):
    def __init__(self):
        self.buffer = []
    def write(self, data):
        self.buffer.append(data)
    
class CapturingStdoutTextTestResult(unittest._TextTestResult):
    def startTest(self, test):
        unittest._TextTestResult.startTest(self, test)
        self._real_stdout = sys.stdout
        self._captured_output = FakeStdout()
        #sys.stdout = codecs.getwriter('utf8')(self._captured_output)
        sys.stdout = self._captured_output

    def stopTest(self, test):
        unittest._TextTestResult.stopTest(self, test)
        sys.stdout = self._real_stdout
        del self._captured_output

    def _exc_info_to_string(self, err, test):
        info = [unittest._TextTestResult._exc_info_to_string(self, err, test)]

        if self._captured_output.buffer:
            info.append("*** Captured output:\n")
            for out in self._captured_output.buffer:
                if isinstance(out, unicode):
                    out = out.encode(self.stream.encoding)
                info.append(out)
            info.append("*** End of captured output.")
        return ''.join(info)

class CapturingStdoutTextTestRunner(unittest.TextTestRunner):
    def _makeResult(self):
        return CapturingStdoutTextTestResult(self.stream, self.descriptions,
                                             self.verbosity)

def run_tests(packages, verbosity=1):
    CapturingStdoutTextTestRunner(verbosity=verbosity).run(get_tests(packages))

def run_with_coverage(function, packages):
    import coverage
    try:
        # Coverage v3 API
        c = coverage.coverage()
    except coverage.CoverageException:
        # Coverage v2 API
        c = coverage

    c.exclude('return NotImplemented')
    c.exclude('raise NotImplementedError')
    c.exclude('except ImportError:')
    c.start()
    function()
    c.stop()
    c.report([werkzeug.import_string(name).__file__ 
              for name in find_all_modules(p for p in packages if p != 'test')])

def profile(function, filename):
    import cProfile
    cProfile.runctx('function()', {}, locals(), filename)
    print "Profile results saved in '%s'" % filename


def main(args=None):
    """Run all doctests and unittests found in ``packages``."""
    if args is None:
        args = sys.argv[1:]
    
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-c', '--coverage', dest='coverage', action='store_true',
                      help='Print a test coverage report')
    parser.add_option('-p', '--profile', dest='profile', action='store_true',
                      help='Run the tests with cProfile and save profile'
                           'data in ./profile_results')
    parser.add_option('-t', '--todo', dest='todo', action='store_true',
                      help='Print the number of occurences of "TODO"')
    parser.add_option("-q", "--quiet",
                      action="store_false", dest="verbose", default=True,
                      help="don't print status messages to stdout")

    (options, packages) = parser.parse_args(args)
    packages = packages or ['kalamar', 'koral', 'kraken', 'test']
    
    import test    
    run = functools.partial(test.run_tests, packages)
    if options.profile:
        run = functools.partial(test.profile, run, 'profile_results')
    if options.coverage:
        run = functools.partial(test.run_with_coverage, run, packages)
        
    run()
    
    if options.todo:
        test.print_TODOs(packages)

