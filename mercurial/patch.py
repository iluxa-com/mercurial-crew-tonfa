# Copyright 2007 Chris Mason <chris.mason@oracle.com>
import base85, cmdutil, mdiff, util, context, revlog, diffhelpers
class PatchError(Exception):
    pass

class NoHunks(PatchError):
    pass

        subject = msg['Subject']
        gitsendmail = 'git-send-email' in msg.get('X-Mailer', '')
        if subject:
            if subject.startswith('[PATCH'):
                pend = subject.find(']')
                    subject = subject[pend+1:].lstrip()
            subject = subject.replace('\n\t', ' ')
            ui.debug('Subject: %s\n' % subject)
        message = ''
                        subject = None
                    elif line == '---' and gitsendmail:
    if subject and not message.startswith(subject):
        message = '%s\n%s' % (subject, message)
def readgitpatch(fp, firstline=None):
    def reader(fp, firstline):
        if firstline is not None:
            yield firstline
        for line in fp:
            yield line

    for line in reader(fp, firstline):
                gp.mode = int(line.rstrip()[-6:], 8)
                gp.mode = int(line.rstrip()[-6:], 8)
def patch(patchname, ui, strip=1, cwd=None, files={}):
    """apply <patchname> to the working directory.
    returns whether patch was applied with fuzz factor."""
    patcher = ui.config('ui', 'patch')
    args = []
    try:
        if patcher:
            return externalpatch(patcher, args, patchname, ui, strip, cwd,
                                 files)
        else:
            try:
                return internalpatch(patchname, ui, strip, cwd, files)
            except NoHunks:
                patcher = util.find_exe('gpatch') or util.find_exe('patch')
                ui.debug('no valid hunks found; trying with %r instead\n' %
                         patcher)
                if util.needbinarypatch():
                    args.append('--binary')
                return externalpatch(patcher, args, patchname, ui, strip, cwd,
                                     files)
    except PatchError, err:
        s = str(err)
        if s:
            raise util.Abort(s)
        else:
            raise util.Abort(_('patch failed to apply'))
def externalpatch(patcher, args, patchname, ui, strip, cwd, files):
    """use <patcher> to apply <patchname> to the working directory.
    returns whether patch was applied with fuzz factor."""
    fuzz = False
    if cwd:
        args.append('-d %s' % util.shellquote(cwd))
    fp = os.popen('%s %s -p%d < %s' % (patcher, ' '.join(args), strip,
                                       util.shellquote(patchname)))

    for line in fp:
        line = line.rstrip()
        ui.note(line + '\n')
        if line.startswith('patching file '):
            pf = util.parse_patch_output(line)
            printed_file = False
            files.setdefault(pf, (None, None))
        elif line.find('with fuzz') >= 0:
            fuzz = True
            if not printed_file:
                ui.warn(pf + '\n')
                printed_file = True
            ui.warn(line + '\n')
        elif line.find('saving rejects to file') >= 0:
            ui.warn(line + '\n')
        elif line.find('FAILED') >= 0:
            if not printed_file:
                ui.warn(pf + '\n')
                printed_file = True
            ui.warn(line + '\n')
    code = fp.close()
    if code:
        raise PatchError(_("patch command failed: %s") %
                         util.explain_exit(code)[0])
    return fuzz
def internalpatch(patchobj, ui, strip, cwd, files={}):
    """use builtin patch to apply <patchobj> to the working directory.
    returns whether patch was applied with fuzz factor."""
    try:
        fp = file(patchobj, 'rb')
    except TypeError:
        fp = patchobj
    if cwd:
        curdir = os.getcwd()
        os.chdir(cwd)
        ret = applydiff(ui, fp, files, strip=strip)
    finally:
        if cwd:
            os.chdir(curdir)
    if ret < 0:
        raise PatchError
    return ret > 0

# @@ -start,len +start,len @@ or @@ -start +start @@ if len is 1
unidesc = re.compile('@@ -(\d+)(,(\d+))? \+(\d+)(,(\d+))? @@')
contextdesc = re.compile('(---|\*\*\*) (\d+)(,(\d+))? (---|\*\*\*)')

class patchfile:
    def __init__(self, ui, fname):
        self.fname = fname
        self.ui = ui
        try:
            fp = file(fname, 'rb')
            self.lines = fp.readlines()
            self.exists = True
        except IOError:
            dirname = os.path.dirname(fname)
            if dirname and not os.path.isdir(dirname):
                dirs = dirname.split(os.path.sep)
                d = ""
                for x in dirs:
                    d = os.path.join(d, x)
                    if not os.path.isdir(d):
                        os.mkdir(d)
            self.lines = []
            self.exists = False

        self.hash = {}
        self.dirty = 0
        self.offset = 0
        self.rej = []
        self.fileprinted = False
        self.printfile(False)
        self.hunks = 0

    def printfile(self, warn):
        if self.fileprinted:
            return
        if warn or self.ui.verbose:
            self.fileprinted = True
        s = _("patching file %s\n") % self.fname
        if warn:
            self.ui.warn(s)
        else:
            self.ui.note(s)


    def findlines(self, l, linenum):
        # looks through the hash and finds candidate lines.  The
        # result is a list of line numbers sorted based on distance
        # from linenum
        def sorter(a, b):
            vala = abs(a - linenum)
            valb = abs(b - linenum)
            return cmp(vala, valb)

        try:
            cand = self.hash[l]
        except:
            return []

        if len(cand) > 1:
            # resort our list of potentials forward then back.
            cand.sort(cmp=sorter)
        return cand

    def hashlines(self):
        self.hash = {}
        for x in xrange(len(self.lines)):
            s = self.lines[x]
            self.hash.setdefault(s, []).append(x)

    def write_rej(self):
        # our rejects are a little different from patch(1).  This always
        # creates rejects in the same form as the original patch.  A file
        # header is inserted so that you can run the reject through patch again
        # without having to type the filename.

        if not self.rej:
            return
        if self.hunks != 1:
            hunkstr = "s"
        else:
            hunkstr = ""

        fname = self.fname + ".rej"
        self.ui.warn(
            _("%d out of %d hunk%s FAILED -- saving rejects to file %s\n") %
            (len(self.rej), self.hunks, hunkstr, fname))
        try: os.unlink(fname)
        except:
            pass
        fp = file(fname, 'wb')
        base = os.path.basename(self.fname)
        fp.write("--- %s\n+++ %s\n" % (base, base))
        for x in self.rej:
            for l in x.hunk:
                fp.write(l)
                if l[-1] != '\n':
                    fp.write("\n\ No newline at end of file\n")

    def write(self, dest=None):
        if self.dirty:
            if not dest:
                dest = self.fname
            st = None
            try:
                st = os.lstat(dest)
                if st.st_nlink > 1:
                    os.unlink(dest)
            except: pass
            fp = file(dest, 'wb')
            if st:
                os.chmod(dest, st.st_mode)
            fp.writelines(self.lines)
            fp.close()

    def close(self):
        self.write()
        self.write_rej()

    def apply(self, h, reverse):
        if not h.complete():
            raise PatchError(_("bad hunk #%d %s (%d %d %d %d)") %
                            (h.number, h.desc, len(h.a), h.lena, len(h.b),
                            h.lenb))

        self.hunks += 1
        if reverse:
            h.reverse()

        if self.exists and h.createfile():
            self.ui.warn(_("file %s already exists\n") % self.fname)
            self.rej.append(h)
            return -1

        if isinstance(h, binhunk):
            if h.rmfile():
                os.unlink(self.fname)
            else:
                self.lines[:] = h.new()
                self.offset += len(h.new())
                self.dirty = 1
            return 0

        # fast case first, no offsets, no fuzz
        old = h.old()
        # patch starts counting at 1 unless we are adding the file
        if h.starta == 0:
            start = 0
        else:
            start = h.starta + self.offset - 1
        orig_start = start
        if diffhelpers.testhunk(old, self.lines, start) == 0:
            if h.rmfile():
                os.unlink(self.fname)
            else:
                self.lines[start : start + h.lena] = h.new()
                self.offset += h.lenb - h.lena
                self.dirty = 1
            return 0

        # ok, we couldn't match the hunk.  Lets look for offsets and fuzz it
        self.hashlines()
        if h.hunk[-1][0] != ' ':
            # if the hunk tried to put something at the bottom of the file
            # override the start line and use eof here
            search_start = len(self.lines)
        else:
            search_start = orig_start

        for fuzzlen in xrange(3):
            for toponly in [ True, False ]:
                old = h.old(fuzzlen, toponly)

                cand = self.findlines(old[0][1:], search_start)
                for l in cand:
                    if diffhelpers.testhunk(old, self.lines, l) == 0:
                        newlines = h.new(fuzzlen, toponly)
                        self.lines[l : l + len(old)] = newlines
                        self.offset += len(newlines) - len(old)
                        self.dirty = 1
                        if fuzzlen:
                            fuzzstr = "with fuzz %d " % fuzzlen
                            f = self.ui.warn
                            self.printfile(True)
                        else:
                            fuzzstr = ""
                            f = self.ui.note
                        offset = l - orig_start - fuzzlen
                        if offset == 1:
                            linestr = "line"
                        else:
                            linestr = "lines"
                        f(_("Hunk #%d succeeded at %d %s(offset %d %s).\n") %
                          (h.number, l+1, fuzzstr, offset, linestr))
                        return fuzzlen
        self.printfile(True)
        self.ui.warn(_("Hunk #%d FAILED at %d\n") % (h.number, orig_start))
        self.rej.append(h)
        return -1

class hunk:
    def __init__(self, desc, num, lr, context):
        self.number = num
        self.desc = desc
        self.hunk = [ desc ]
        self.a = []
        self.b = []
        if context:
            self.read_context_hunk(lr)
        else:
            self.read_unified_hunk(lr)

    def read_unified_hunk(self, lr):
        m = unidesc.match(self.desc)
        if not m:
            raise PatchError(_("bad hunk #%d") % self.number)
        self.starta, foo, self.lena, self.startb, foo2, self.lenb = m.groups()
        if self.lena == None:
            self.lena = 1
        else:
            self.lena = int(self.lena)
        if self.lenb == None:
            self.lenb = 1
        else:
            self.lenb = int(self.lenb)
        self.starta = int(self.starta)
        self.startb = int(self.startb)
        diffhelpers.addlines(lr.fp, self.hunk, self.lena, self.lenb, self.a, self.b)
        # if we hit eof before finishing out the hunk, the last line will
        # be zero length.  Lets try to fix it up.
        while len(self.hunk[-1]) == 0:
                del self.hunk[-1]
                del self.a[-1]
                del self.b[-1]
                self.lena -= 1
                self.lenb -= 1

    def read_context_hunk(self, lr):
        self.desc = lr.readline()
        m = contextdesc.match(self.desc)
        if not m:
            raise PatchError(_("bad hunk #%d") % self.number)
        foo, self.starta, foo2, aend, foo3 = m.groups()
        self.starta = int(self.starta)
        if aend == None:
            aend = self.starta
        self.lena = int(aend) - self.starta
        if self.starta:
            self.lena += 1
        for x in xrange(self.lena):
            l = lr.readline()
            if l.startswith('---'):
                lr.push(l)
                break
            s = l[2:]
            if l.startswith('- ') or l.startswith('! '):
                u = '-' + s
            elif l.startswith('  '):
                u = ' ' + s
            else:
                raise PatchError(_("bad hunk #%d old text line %d") %
                                 (self.number, x))
            self.a.append(u)
            self.hunk.append(u)

        l = lr.readline()
        if l.startswith('\ '):
            s = self.a[-1][:-1]
            self.a[-1] = s
            self.hunk[-1] = s
            l = lr.readline()
        m = contextdesc.match(l)
        if not m:
            raise PatchError(_("bad hunk #%d") % self.number)
        foo, self.startb, foo2, bend, foo3 = m.groups()
        self.startb = int(self.startb)
        if bend == None:
            bend = self.startb
        self.lenb = int(bend) - self.startb
        if self.startb:
            self.lenb += 1
        hunki = 1
        for x in xrange(self.lenb):
            l = lr.readline()
            if l.startswith('\ '):
                s = self.b[-1][:-1]
                self.b[-1] = s
                self.hunk[hunki-1] = s
            if not l:
                lr.push(l)
                break
            s = l[2:]
            if l.startswith('+ ') or l.startswith('! '):
                u = '+' + s
            elif l.startswith('  '):
                u = ' ' + s
            elif len(self.b) == 0:
                # this can happen when the hunk does not add any lines
                lr.push(l)
                break
            else:
                raise PatchError(_("bad hunk #%d old text line %d") %
                                 (self.number, x))
            self.b.append(s)
            while True:
                if hunki >= len(self.hunk):
                    h = ""
                else:
                    h = self.hunk[hunki]
                hunki += 1
                if h == u:
                    break
                elif h.startswith('-'):
                    continue
                else:
                    self.hunk.insert(hunki-1, u)
                    break

        if not self.a:
            # this happens when lines were only added to the hunk
            for x in self.hunk:
                if x.startswith('-') or x.startswith(' '):
                    self.a.append(x)
        if not self.b:
            # this happens when lines were only deleted from the hunk
            for x in self.hunk:
                if x.startswith('+') or x.startswith(' '):
                    self.b.append(x[1:])
        # @@ -start,len +start,len @@
        self.desc = "@@ -%d,%d +%d,%d @@\n" % (self.starta, self.lena,
                                             self.startb, self.lenb)
        self.hunk[0] = self.desc

    def reverse(self):
        origlena = self.lena
        origstarta = self.starta
        self.lena = self.lenb
        self.starta = self.startb
        self.lenb = origlena
        self.startb = origstarta
        self.a = []
        self.b = []
        # self.hunk[0] is the @@ description
        for x in xrange(1, len(self.hunk)):
            o = self.hunk[x]
            if o.startswith('-'):
                n = '+' + o[1:]
                self.b.append(o[1:])
            elif o.startswith('+'):
                n = '-' + o[1:]
                self.a.append(n)
            else:
                n = o
                self.b.append(o[1:])
                self.a.append(o)
            self.hunk[x] = o

    def fix_newline(self):
        diffhelpers.fix_newline(self.hunk, self.a, self.b)

    def complete(self):
        return len(self.a) == self.lena and len(self.b) == self.lenb

    def createfile(self):
        return self.starta == 0 and self.lena == 0

    def rmfile(self):
        return self.startb == 0 and self.lenb == 0

    def fuzzit(self, l, fuzz, toponly):
        # this removes context lines from the top and bottom of list 'l'.  It
        # checks the hunk to make sure only context lines are removed, and then
        # returns a new shortened list of lines.
        fuzz = min(fuzz, len(l)-1)
        if fuzz:
            top = 0
            bot = 0
            hlen = len(self.hunk)
            for x in xrange(hlen-1):
                # the hunk starts with the @@ line, so use x+1
                if self.hunk[x+1][0] == ' ':
                    top += 1
                else:
                    break
            if not toponly:
                for x in xrange(hlen-1):
                    if self.hunk[hlen-bot-1][0] == ' ':
                        bot += 1
                    else:
                        break
            # top and bot now count context in the hunk
            # adjust them if either one is short
            context = max(top, bot, 3)
            if bot < context:
                bot = max(0, fuzz - (context - bot))
            else:
                bot = min(fuzz, bot)
            if top < context:
                top = max(0, fuzz - (context - top))
            else:
                top = min(fuzz, top)
            return l[top:len(l)-bot]
        return l
    def old(self, fuzz=0, toponly=False):
        return self.fuzzit(self.a, fuzz, toponly)
    def newctrl(self):
        res = []
        for x in self.hunk:
            c = x[0]
            if c == ' ' or c == '+':
                res.append(x)
        return res
    def new(self, fuzz=0, toponly=False):
        return self.fuzzit(self.b, fuzz, toponly)
class binhunk:
    'A binary patch file. Only understands literals so far.'
    def __init__(self, gitpatch):
        self.gitpatch = gitpatch
        self.text = None
        self.hunk = ['GIT binary patch\n']
    def createfile(self):
        return self.gitpatch.op in ('ADD', 'RENAME', 'COPY')
    def rmfile(self):
        return self.gitpatch.op == 'DELETE'
    def complete(self):
        return self.text is not None
    def new(self):
        return [self.text]

    def extract(self, fp):
        line = fp.readline()
        self.hunk.append(line)
        while line and not line.startswith('literal '):
            line = fp.readline()
            self.hunk.append(line)
        if not line:
            raise PatchError(_('could not extract binary patch'))
        size = int(line[8:].rstrip())
        dec = []
        line = fp.readline()
        self.hunk.append(line)
        while len(line) > 1:
            l = line[0]
            if l <= 'Z' and l >= 'A':
                l = ord(l) - ord('A') + 1
            else:
                l = ord(l) - ord('a') + 27
            dec.append(base85.b85decode(line[1:-1])[:l])
            line = fp.readline()
            self.hunk.append(line)
        text = zlib.decompress(''.join(dec))
        if len(text) != size:
            raise PatchError(_('binary patch is %d bytes, not %d') %
                             len(text), size)
        self.text = text

def parsefilename(str):
    # --- filename \t|space stuff
    s = str[4:]
    i = s.find('\t')
    if i < 0:
        i = s.find(' ')
        if i < 0:
            return s
    return s[:i]

def selectfile(afile_orig, bfile_orig, hunk, strip, reverse):
    def pathstrip(path, count=1):
        pathlen = len(path)
        i = 0
        if count == 0:
            return path.rstrip()
        while count > 0:
            i = path.find('/', i)
            if i == -1:
                raise PatchError(_("unable to strip away %d dirs from %s") %
                                 (count, path))
            i += 1
            # consume '//' in the path
            while i < pathlen - 1 and path[i] == '/':
                i += 1
            count -= 1
        return path[i:].rstrip()

    nulla = afile_orig == "/dev/null"
    nullb = bfile_orig == "/dev/null"
    afile = pathstrip(afile_orig, strip)
    gooda = os.path.exists(afile) and not nulla
    bfile = pathstrip(bfile_orig, strip)
    if afile == bfile:
        goodb = gooda
    else:
        goodb = os.path.exists(bfile) and not nullb
    createfunc = hunk.createfile
    if reverse:
        createfunc = hunk.rmfile
    if not goodb and not gooda and not createfunc():
        raise PatchError(_("unable to find %s or %s for patching") %
                         (afile, bfile))
    if gooda and goodb:
        fname = bfile
        if afile in bfile:
            fname = afile
    elif gooda:
        fname = afile
    elif not nullb:
        fname = bfile
        if afile in bfile:
            fname = afile
    elif not nulla:
        fname = afile
    return fname

class linereader:
    # simple class to allow pushing lines back into the input stream
    def __init__(self, fp):
        self.fp = fp
        self.buf = []

    def push(self, line):
        self.buf.append(line)

    def readline(self):
        if self.buf:
            l = self.buf[0]
            del self.buf[0]
            return l
        return self.fp.readline()

def applydiff(ui, fp, changed, strip=1, sourcefile=None, reverse=False,
              rejmerge=None, updatedir=None):
    """reads a patch from fp and tries to apply it.  The dict 'changed' is
       filled in with all of the filenames changed by the patch.  Returns 0
       for a clean patch, -1 if any rejects were found and 1 if there was
       any fuzz."""

    def scangitpatch(fp, firstline, cwd=None):
        '''git patches can modify a file, then copy that file to
        a new file, but expect the source to be the unmodified form.
        So we scan the patch looking for that case so we can do
        the copies ahead of time.'''

        pos = 0
        try:
            pos = fp.tell()
        except IOError:
            fp = cStringIO.StringIO(fp.read())

        (dopatch, gitpatches) = readgitpatch(fp, firstline)
        for gp in gitpatches:
            if gp.op in ('COPY', 'RENAME'):
                copyfile(gp.oldpath, gp.path, basedir=cwd)

        fp.seek(pos)

        return fp, dopatch, gitpatches

    current_hunk = None
    current_file = None
    afile = ""
    bfile = ""
    state = None
    hunknum = 0
    rejects = 0

    git = False
    gitre = re.compile('diff --git (a/.*) (b/.*)')

    # our states
    BFILE = 1
    err = 0
    context = None
    lr = linereader(fp)
    dopatch = True
    gitworkdone = False

    while True:
        newfile = False
        x = lr.readline()
        if not x:
            break
        if current_hunk:
            if x.startswith('\ '):
                current_hunk.fix_newline()
            ret = current_file.apply(current_hunk, reverse)
            if ret >= 0:
                changed.setdefault(current_file.fname, (None, None))
                if ret > 0:
                    err = 1
            current_hunk = None
            gitworkdone = False
        if ((sourcefile or state == BFILE) and ((not context and x[0] == '@') or
            ((context or context == None) and x.startswith('***************')))):
            try:
                if context == None and x.startswith('***************'):
                    context = True
                current_hunk = hunk(x, hunknum + 1, lr, context)
            except PatchError, err:
                ui.debug(err)
                current_hunk = None
                continue
            hunknum += 1
            if not current_file:
                if sourcefile:
                    current_file = patchfile(ui, sourcefile)
                else:
                    current_file = selectfile(afile, bfile, current_hunk,
                                              strip, reverse)
                    current_file = patchfile(ui, current_file)
        elif state == BFILE and x.startswith('GIT binary patch'):
            current_hunk = binhunk(changed[bfile[2:]][1])
            if not current_file:
                if sourcefile:
                    current_file = patchfile(ui, sourcefile)
                else:
                    current_file = selectfile(afile, bfile, current_hunk,
                                              strip, reverse)
                    current_file = patchfile(ui, current_file)
            hunknum += 1
            current_hunk.extract(fp)
        elif x.startswith('diff --git'):
            # check for git diff, scanning the whole patch file if needed
            m = gitre.match(x)
            if m:
                afile, bfile = m.group(1, 2)
                if not git:
                    git = True
                    fp, dopatch, gitpatches = scangitpatch(fp, x)
                    for gp in gitpatches:
                        changed[gp.path] = (gp.op, gp)
                # else error?
                # copy/rename + modify should modify target, not source
                if changed.get(bfile[2:], (None, None))[0] in ('COPY',
                                                               'RENAME'):
                    afile = bfile
                    gitworkdone = True
            newfile = True
        elif x.startswith('---'):
            # check for a unified diff
            l2 = lr.readline()
            if not l2.startswith('+++'):
                lr.push(l2)
                continue
            newfile = True
            context = False
            afile = parsefilename(x)
            bfile = parsefilename(l2)
        elif x.startswith('***'):
            # check for a context diff
            l2 = lr.readline()
            if not l2.startswith('---'):
                lr.push(l2)
                continue
            l3 = lr.readline()
            lr.push(l3)
            if not l3.startswith("***************"):
                lr.push(l2)
                continue
            newfile = True
            context = True
            afile = parsefilename(x)
            bfile = parsefilename(l2)

        if newfile:
            if current_file:
                current_file.close()
                if rejmerge:
                    rejmerge(current_file)
                rejects += len(current_file.rej)
            state = BFILE
            current_file = None
            hunknum = 0
    if current_hunk:
        if current_hunk.complete():
            ret = current_file.apply(current_hunk, reverse)
            if ret >= 0:
                changed.setdefault(current_file.fname, (None, None))
                if ret > 0:
                    err = 1
        else:
            fname = current_file and current_file.fname or None
            raise PatchError(_("malformed patch %s %s") % (fname,
                             current_hunk.desc))
    if current_file:
        current_file.close()
        if rejmerge:
            rejmerge(current_file)
        rejects += len(current_file.rej)
    if updatedir and git:
        updatedir(gitpatches)
    if rejects:
        return -1
    if hunknum == 0 and dopatch and not gitworkdone:
        raise NoHunks
    return err
def updatedir(ui, repo, patches):
            copies.append((gp.oldpath, gp.path))
            copies.append((gp.oldpath, gp.path))
    for src, dst in copies:
        repo.copy(src, dst)
        repo.remove(removes, True)
            l = gp.mode & 020000 != 0
                util.set_link(dst, l)
                if not l:
                    util.set_exec(dst, x)
    cmdutil.addremove(repo, cfiles)
def b85diff(to, tn):
        linkf2 = ctx2.manifest().linkf
        linkf2 = util.linkfunc(repo.root, None)
            mc = ctx2.parents()[0].manifest().copy()
            execf2 = mc.execf
            linkf2 = mc.linkf
    # This will only really work if c1 is the Nth 1st parent of c2.
    def renamed(c1, c2, man, f):
        startrev = c1.rev()
        c = c2
        files = (f,)
            if f in files:
            files = c.files()
        if f not in man:
        c1, c2 = ctx1, ctx2
        files = added
        man = man1
        if node2 and ctx1.rev() >= ctx2.rev():
            # renamed() starts at c2 and walks back in history until c1.
            # Since ctx1.rev() >= ctx2.rev(), invert ctx2 and ctx1 to
            # detect (inverted) copies.
            c1, c2 = ctx2, ctx1
            files = removed
            man = ctx2.manifest()
        for f in files:
            src = renamed(c1, c2, man, f)
        if ctx1 == c2:
            # invert the copied dict
            copied = dict([(v, k) for (k, v) in copied.iteritems()])
        # If we've renamed file foo to bar (copied['bar'] = 'foo'),
        # avoid showing a diff for foo if we're going to show
        # the rename to bar.
        srcs = [x[1] for x in copied.iteritems() if x[0] in added]
            def gitmode(x, l):
                return l and '120000' or (x and '100755' or '100644')
                mode = gitmode(execf2(f), linkf2(f))
                    omode = gitmode(man1.execf(a), man1.linkf(a))
                    mode = gitmode(man1.execf(f), man1.linkf(f))
                omode = gitmode(man1.execf(f), man1.linkf(f))
                nmode = gitmode(execf2(f), linkf2(f))
                text = b85diff(to, tn)