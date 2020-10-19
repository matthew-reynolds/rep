#!/usr/bin/env python
"""Convert REPs to (X)HTML - courtesy of /F.

Usage: %(PROGRAM)s [options] [<reps> ...]

Options:

-u, --user
    python.org username

-b, --browse
    After generating the HTML, direct your web browser to view it
    (using the Python webbrowser module).  If both -i and -b are
    given, this will browse the on-line HTML; otherwise it will
    browse the local HTML.  If no rep arguments are given, this
    will browse REP 0.

-i, --install
    After generating the HTML, install it and the plaintext source file
    (.rst) on python.org.  In that case the user's name is used in the scp
    and ssh commands, unless "-u username" is given (in which case, it is
    used instead).  Without -i, -u is ignored.

-l, --local
    Same as -i/--install, except install on the local machine.  Use this
    when logged in to the python.org machine (dinsdale).

-q, --quiet
    Turn off verbose messages.

-h, --help
    Print this help message and exit.

The optional arguments ``reps`` are either rep numbers or .rst files.
"""

from __future__ import print_function

import sys
import os
import re
import cgi
import glob
import getopt
import errno
import time

REQUIRES = {'python': '2.2',
            'docutils': '0.2.7'}
PROGRAM = sys.argv[0]
RFCURL = 'http://www.faqs.org/rfcs/rfc%d.html'
REPURL = 'rep-%04d.html'
REPGITURL = (
    'https://github.com/ros-infrastructure/rep/blob/master/rep-%04d.rst')
REPDIRRUL = 'http://www.ros.org/reps/'

HOST = "wgs32.willowgarage.com"                    # host for update
HDIR = "/var/www/www.ros.org/html/reps"  # target host directory
LOCALVARS = "Local Variables:"

COMMENT = """<!--
This HTML is auto-generated.  DO NOT EDIT THIS FILE!  If you are writing a new
REP, see https://ros.org/reps/rep-0001.html for instructions and links
to templates.  DO NOT USE THIS HTML FILE AS YOUR TEMPLATE!
-->"""

# The generated HTML doesn't validate -- you cannot use <hr> and <h3> inside
# <pre> tags.  But if I change that, the result doesn't look very nice...
DTD = ('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN"\n'
       '                      "http://www.w3.org/TR/REC-html40/loose.dtd">')

fixpat = re.compile(
    "((https?|ftp):[-_a-zA-Z0-9/.+~:?#$=&,]+)|(rep-\d+(.rst)?)|"
    "(RFC[- ]?(?P<rfcnum>\d+))|"
    "(REP\s+(?P<repnum>\d+))|"
    ".")

EMPTYSTRING = ''
SPACE = ' '
COMMASPACE = ', '

# Hotpatch docutils as PEP is actually a special module
# inside. Forgive this hack, but docutils does not appear to be
# pluggable.
import docutils.readers
import docutils.writers
import docutils_readers_rep
import docutils_writers_rep
sys.modules['docutils.readers.rep'] = docutils_readers_rep
sys.modules['docutils.writers.rep_html'] = docutils_writers_rep


def usage(code, msg=''):
    """Print usage message and exit.  Uses stderr if code != 0."""
    if code == 0:
        out = sys.stdout
    else:
        out = sys.stderr
    print(__doc__ % globals(), file=out)
    if msg:
        print(msg, file=out)
    sys.exit(code)


def fixanchor(current, match):
    text = match.group(0)
    link = None
    if (text.startswith('http:') or text.startswith('https:') or
            text.startswith('ftp:')):
        # Strip off trailing punctuation.  Pattern taken from faqwiz.
        ltext = list(text)
        while ltext:
            c = ltext.pop()
            if c not in '();:,.?\'"<>':
                ltext.append(c)
                break
        link = EMPTYSTRING.join(ltext)
    elif text.startswith('rep-') and text != current:
        link = os.path.splitext(text)[0] + ".html"
    elif text.startswith('REP'):
        repnum = int(match.group('repnum'))
        link = REPURL % repnum
    elif text.startswith('RFC'):
        rfcnum = int(match.group('rfcnum'))
        link = RFCURL % rfcnum
    if link:
        return '<a href="%s">%s</a>' % (cgi.escape(link), cgi.escape(text))
    return cgi.escape(match.group(0))  # really slow, but it works...


NON_MASKED_EMAILS = [
    'ros-users@code.ros.org',
    'ros-developers@code.ros.org',
    ]


def fixemail(address, repno):
    if address.lower() in NON_MASKED_EMAILS:
        # return hyperlinked version of email address
        return linkemail(address, repno)
    else:
        # return masked version of email address
        parts = address.split('@', 1)
        return '%s&#32;&#97;t&#32;%s' % (parts[0], parts[1])


def linkemail(address, repno):
    parts = address.split('@', 1)
    return ('<a href="mailto:%s&#64;%s?subject=REP%%20%s">'
            '%s&#32;&#97;t&#32;%s</a>'
            % (parts[0], parts[1], repno, parts[0], parts[1]))


def fixfile(inpath, input_lines, outfile):
    from email.utils import parseaddr
    basename = os.path.basename(inpath)
    infile = iter(input_lines)
    if 0:
        # convert plaintext rep to minimal XHTML markup
        print(DTD, file=outfile)
        print('<html>', file=outfile)
        print(COMMENT, file=outfile)
        print('<head>', file=outfile)
    # head
    header = []
    rep = ""
    title = ""
    for line in infile:
        if not line.strip():
            break
        if line[0].strip():
            if ":" not in line:
                break
            key, value = line.split(":", 1)
            value = value.strip()
            header.append((key, value))
        else:
            # continuation line
            key, value = header[-1]
            value = value + line
            header[-1] = key, value
        if key.lower() == "title":
            title = value
        elif key.lower() == "rep":
            rep = value
    if rep:
        title = "REP " + rep + " -- " + title

    # remove nav to rep index
    f = open('rep-html-template', 'r')
    tmpl = f.read()
    f.close()
    if int(rep) == 0:
        tmpl = tmpl.replace(
            '[<b><a href="%(repindex)s">REP Index</a></b>]', '')
    tmpl_vars = {
        'repindex': 'rep-0000.html',
        'rep': title,
        'repnum': "%04d" % int(rep),
        'rephome': '/reps',
        'encoding': 'utf-8',
        'version': '',
        'title': 'REP '+rep+" -- "+title,
        'stylesheet': (
            '<link rel="stylesheet" href="css/rep.css" type="text/css" />'),
        }

    real_outfile = outfile

    try:
        from cStringIO import StringIO
    except ImportError:
        from io import StringIO
    outfile = StringIO()
    print("""<div class="header">
<table border="0" class="rfc2822 docutils field-list" frame="void" rules="none">
<col class="field-name" />
<col class="field-body" />
<tbody valign="top">""", file=outfile)
    for k, v in header:
        if k.lower() in ('author', 'discussions-to'):
            mailtos = []
            for part in re.split(',\s*', v):
                if '@' in part:
                    realname, addr = parseaddr(part)
                    if k.lower() == 'discussions-to':
                        m = linkemail(addr, rep)
                    else:
                        m = fixemail(addr, rep)
                    mailtos.append('%s &lt;%s&gt;' % (realname, m))
                elif part.startswith('http:'):
                    mailtos.append(
                        '<a href="%s">%s</a>' % (part, part))
                else:
                    mailtos.append(part)
            v = COMMASPACE.join(mailtos)
        elif k.lower() in ('replaces', 'replaced-by', 'requires'):
            otherreps = ''
            for otherrep in re.split(',?\s+', v):
                otherrep = int(otherrep)
                otherreps += '<a href="rep-%04d.html">%i</a> ' % (otherrep,
                                                                  otherrep)
            v = otherreps
        elif k.lower() in ('last-modified',):
            date = v or time.strftime('%d-%b-%Y',
                                      time.localtime(os.stat(inpath)[8]))
            try:
                url = REPGITURL % int(rep)
                v = '<a href="%s">%s</a> ' % (url, cgi.escape(date))
            except ValueError as error:
                v = date
        elif k.lower() in ('content-type',):
            url = REPURL % 9
            rep_type = v or 'text/plain'
            v = '<a href="%s">%s</a> ' % (url, cgi.escape(rep_type))
        else:
            v = cgi.escape(v)
        print(('  <tr class="field"><th class="field-name">%s:&nbsp;</th>' +
               '<td class="field-body">%s</td></tr>') %
              (cgi.escape(k), v), file=outfile)
    print('</table>', file=outfile)
    print('</div>', file=outfile)
    print('<hr />', file=outfile)
    print('<div class="content">', file=outfile)
    need_pre = 1
    for line in infile:
        if line[0] == '\f':
            continue
        if line.strip() == LOCALVARS:
            break
        if line[0].strip():
            if not need_pre:
                print('</pre>', file=outfile)
            print('<h3>%s</h3>' % line.strip(), file=outfile)
            need_pre = 1
        elif not line.strip() and need_pre:
            continue
        else:
            # REP 0 has some special treatment
            if basename == 'rep-0000.rst':
                parts = line.split()
                if len(parts) > 1 and re.match(r'\s*\d{1,4}', parts[1]):
                    # This is a REP summary line, which we need to hyperlink
                    url = REPURL % int(parts[1])
                    if need_pre:
                        print('<pre>', file=outfile)
                        need_pre = 0
                    print(re.sub(
                        parts[1],
                        '<a href="%s">%s</a>' % (url, parts[1]),
                        line.rstrip(), 1), file=outfile)
                    continue
                elif parts and '@' in parts[-1]:
                    # This is a rep email address line, so filter it.
                    url = fixemail(parts[-1], rep)
                    if need_pre:
                        print('<pre>', file=outfile)
                        need_pre = 0
                    print(re.sub(
                        parts[-1], url, line.rstrip(), 1), file=outfile)
                    continue
            line = fixpat.sub(lambda x, c=inpath: fixanchor(c, x), line)
            if need_pre:
                print('<pre>', file=outfile)
                need_pre = 0
            outfile.write(line)
    if not need_pre:
        print('</pre>', file=outfile)

    print('</div>', file=outfile)

    tmpl_vars['body'] = outfile.getvalue()
    real_outfile.write((tmpl % tmpl_vars).encode('utf'))
    if 0:
        print('</body>', file=outfile)
        print('</html>', file=outfile)

docutils_settings = None
"""Runtime settings object used by Docutils.  Can be set by the client
application when this module is imported."""


def fix_rst_rep(inpath, input_lines, outfile):
    from docutils import core
    output = core.publish_string(
        source=''.join(input_lines),
        source_path=inpath,
        destination_path=outfile.name,
        reader_name='rep',
        parser_name='restructuredtext',
        writer_name='rep_html',
        settings=docutils_settings,
        # Allow Docutils traceback if there's an exception:
        settings_overrides={'traceback': 1})
    outfile.write(output)


def get_rep_type(input_lines):
    """
    Return the Content-Type of the input.  "text/plain" is the default.

    Return ``None`` if the input is not a REP.
    """
    rep_type = None
    for line in input_lines:
        line = line.rstrip().lower()
        if not line:
            # End of the RFC 2822 header (first blank line).
            break
        elif line.startswith('content-type: '):
            rep_type = line.split()[1] or 'text/plain'
            break
        elif line.startswith('rep: '):
            # Default REP type, used if no explicit content-type specified:
            rep_type = 'text/plain'
    return rep_type


def get_input_lines(inpath):
    try:
        infile = open(inpath)
    except IOError as e:
        if e.errno != errno.ENOENT:
            raise
        print('Error: Skipping missing REP file:', e.filename, file=sys.stderr)
        sys.stderr.flush()
        return None
    lines = infile.read().splitlines(1)  # handles x-platform line endings
    infile.close()
    return lines


def find_rep(rep_str):
    """Find the .rst file indicated by a cmd line argument."""
    if os.path.exists(rep_str):
        return rep_str
    num = int(rep_str)
    return "rep-%04d.rst" % num


def make_html(inpath, verbose=0):
    input_lines = get_input_lines(inpath)
    if input_lines is None:
        return None
    rep_type = get_rep_type(input_lines)
    if rep_type is None:
        print('Error: Input file %s is not a REP.' % inpath, file=sys.stderr)
        sys.stdout.flush()
        return None
    elif rep_type not in REP_TYPE_DISPATCH:
        print('Error: Unknown REP type for input file %s: %s' %
              (inpath, rep_type), file=sys.stderr)
        sys.stdout.flush()
        return None
    elif REP_TYPE_DISPATCH[rep_type] is None:
        rep_type_error(inpath, rep_type)
        return None
    outpath = os.path.splitext(inpath)[0] + ".html"
    if verbose:
        print(inpath, "(%s)" % rep_type, "->", outpath)
        sys.stdout.flush()
    outfile = open(outpath, "wb")
    REP_TYPE_DISPATCH[rep_type](inpath, input_lines, outfile)
    outfile.close()
    os.chmod(outfile.name, 0o664)
    return outpath


def push_rep(htmlfiles, rstfiles, username, verbose, local=0):
    quiet = ""
    if local:
        if verbose:
            quiet = "-v"
        target = HDIR
        copy_cmd = "cp"
        #chmod_cmd = "chmod"
    else:
        if not verbose:
            quiet = "-q"
        if username:
            username = username + "@"
        target = username + HOST + ":" + HDIR
        copy_cmd = "scp"
        #chmod_cmd = "ssh %s%s chmod" % (username, HOST)
    files = htmlfiles[:]
    files.extend(rstfiles)
    files.append("css/rep.css")
    filelist = SPACE.join(files)
    rc = os.system("%s %s %s %s" % (copy_cmd, quiet, filelist, target))
    if rc:
        sys.exit(rc)
##    rc = os.system("%s 664 %s/*" % (chmod_cmd, HDIR))
##    if rc:
##        sys.exit(rc)

REP_TYPE_DISPATCH = {'text/plain': fixfile,
                     'text/x-rst': fix_rst_rep}
REP_TYPE_MESSAGES = {}


def check_requirements():
    # Check Python:
    try:
        from email.utils import parseaddr
    except ImportError:
        REP_TYPE_DISPATCH['text/plain'] = None
        REP_TYPE_MESSAGES['text/plain'] = (
            'Python %s or better required for "%%(rep_type)s" REP '
            'processing; %s present (%%(inpath)s).'
            % (REQUIRES['python'], sys.version.split()[0]))
    # Check Docutils:
    try:
        import docutils
    except ImportError:
        REP_TYPE_DISPATCH['text/x-rst'] = None
        REP_TYPE_MESSAGES['text/x-rst'] = (
            'Docutils not present for "%(rep_type)s" REP file %(inpath)s.  '
            'See README.txt for installation.')
    else:
        installed = [int(part) for part in docutils.__version__.split('.')]
        required = [int(part) for part in REQUIRES['docutils'].split('.')]
        if installed < required:
            REP_TYPE_DISPATCH['text/x-rst'] = None
            REP_TYPE_MESSAGES['text/x-rst'] = (
                'Docutils must be reinstalled for "%%(rep_type)s" REP '
                'processing (%%(inpath)s).  Version %s or better required; '
                '%s present.  See README.txt for installation.'
                % (REQUIRES['docutils'], docutils.__version__))


def rep_type_error(inpath, rep_type):
    print('Error: ' + REP_TYPE_MESSAGES[rep_type] % locals(), file=sys.stderr)
    sys.stdout.flush()


def browse_file(rep):
    import webbrowser
    file = find_rep(rep)
    if file.endswith(".rst"):
        file = file[:-3] + "html"
    file = os.path.abspath(file)
    url = "file:" + file
    webbrowser.open(url)


def browse_remote(rep):
    import webbrowser
    file = find_rep(rep)
    if file.endswith(".rst"):
        file = file[:-3] + "html"
    url = REPDIRRUL + file
    webbrowser.open(url)


def main(argv=None):
    # defaults
    update = 0
    local = 0
    username = ''
    verbose = 1
    browse = 0

    check_requirements()

    if argv is None:
        argv = sys.argv[1:]

    try:
        opts, args = getopt.getopt(
            argv, 'bilhqu:',
            ['browse', 'install', 'local', 'help', 'quiet', 'user='])
    except getopt.error as msg:
        usage(1, msg)

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage(0)
        elif opt in ('-i', '--install'):
            update = 1
        elif opt in ('-l', '--local'):
            update = 1
            local = 1
        elif opt in ('-u', '--user'):
            username = arg
        elif opt in ('-q', '--quiet'):
            verbose = 0
        elif opt in ('-b', '--browse'):
            browse = 1

    if args:
        reprst = []
        html = []
        for rep in args:
            file = find_rep(rep)
            reprst.append(file)
            newfile = make_html(file, verbose=verbose)
            if newfile:
                html.append(newfile)
                if browse and not update:
                    browse_file(rep)
    else:
        # do them all
        reprst = []
        html = []
        files = glob.glob("rep-*.rst")
        files.sort()
        for file in files:
            reprst.append(file)
            newfile = make_html(file, verbose=verbose)
            if newfile:
                html.append(newfile)
        if browse and not update:
            browse_file("0")

    if update:
        push_rep(html, reprst, username, verbose, local=local)
        if browse:
            if args:
                for rep in args:
                    browse_remote(rep)
            else:
                browse_remote("0")


if __name__ == "__main__":
    main()
