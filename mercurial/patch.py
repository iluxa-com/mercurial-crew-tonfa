from node import hex, nullid, short
import base85, cmdutil, mdiff, util, context, revlog, diffhelpers, copies
import cStringIO, email.Parser, os, popen2, re, sha, errno
    fp = util.popen('%s %s -p%d < %s' % (patcher, ' '.join(args), strip,
    def __init__(self, ui, fname, missing=False):
        self.lines = []
        self.exists = False
        self.missing = missing
        if not missing:
            try:
                fp = file(fname, 'rb')
                self.lines = fp.readlines()
                self.exists = True
            except IOError:
                pass
        else:
            self.ui.warn(_("unable to find '%s' for patching\n") % self.fname)

        if not self.exists:
                os.makedirs(dirname)
            cand.sort(sorter)
            except OSError, inst:
                if inst.errno != errno.ENOENT:
                    raise
            if st and st.st_nlink > 1:
                os.unlink(dest)
            if st and st.st_nlink > 1:
        if self.missing:
            self.rej.append(h)
            return -1

    def __init__(self, desc, num, lr, context, create=False, remove=False):
        self.create = create
        self.remove = remove and not create
        self.create, self.remove = self.remove, self.create
        return self.starta == 0 and self.lena == 0 and self.create
        return self.startb == 0 and self.lenb == 0 and self.remove
    s = str[4:].rstrip('\r\n')
        return path[:i].lstrip(), path[i:].rstrip()
    abase, afile = pathstrip(afile_orig, strip)
    gooda = not nulla and os.path.exists(afile)
    bbase, bfile = pathstrip(bfile_orig, strip)
        goodb = not nullb and os.path.exists(bfile)
    missing = not goodb and not gooda and not createfunc()
    # If afile is "a/b/foo" and bfile is "a/b/foo.orig" we assume the
    # diff is between a file and its backup. In this case, the original
    # file should be patched (see original mpatch code).
    isbackup = (abase == bbase and bfile.startswith(afile))
    fname = None
    if not missing:
        if gooda and goodb:
            fname = isbackup and afile or bfile
        elif gooda:

    if not fname:
        if not nullb:
            fname = isbackup and afile or bfile
        elif not nulla:
        else:
            raise PatchError(_("undefined source and destination files"))

    return fname, missing
def iterhunks(ui, fp, sourcefile=None):
    """Read a patch and yield the following events:
    - ("file", afile, bfile, firsthunk): select a new target file.
    - ("hunk", hunk): a new hunk is ready to be applied, follows a
    "file" event.
    - ("git", gitchanges): current diff is in git format, gitchanges
    maps filenames to gitpatch records. Unique event.
    """
    def scangitpatch(fp, firstline):
    changed = {}
    emitfile = False
    # gitworkdone is True if a git operation (copy, rename, ...) was
    # performed already for the current file. Useful when the file
    # section may have no hunk.
            yield 'hunk', current_hunk
                gpatch = changed.get(bfile[2:], (None, None))[1]
                create = afile == '/dev/null' or gpatch and gpatch.op == 'ADD'
                remove = bfile == '/dev/null' or gpatch and gpatch.op == 'DELETE'
                current_hunk = hunk(x, hunknum + 1, lr, context, create, remove)
            if emitfile:
                emitfile = False
                yield 'file', (afile, bfile, current_hunk)
            if emitfile:
                emitfile = False
                yield 'file', (afile, bfile, current_hunk)
                    yield 'git', gitpatches
                gitop = changed.get(bfile[2:], (None, None))[0]
                if gitop in ('COPY', 'DELETE', 'RENAME'):
            emitfile = True
            yield 'hunk', current_hunk
        else:
            raise PatchError(_("malformed patch %s %s") % (afile,
                             current_hunk.desc))

    if hunknum == 0 and dopatch and not gitworkdone:
        raise NoHunks

def applydiff(ui, fp, changed, strip=1, sourcefile=None, reverse=False,
              rejmerge=None, updatedir=None):
    """reads a patch from fp and tries to apply it.  The dict 'changed' is
       filled in with all of the filenames changed by the patch.  Returns 0
       for a clean patch, -1 if any rejects were found and 1 if there was
       any fuzz."""

    rejects = 0
    err = 0
    current_file = None
    gitpatches = None

    def closefile():
        if not current_file:
            return 0
        current_file.close()
        if rejmerge:
            rejmerge(current_file)
        return len(current_file.rej)

    for state, values in iterhunks(ui, fp, sourcefile):
        if state == 'hunk':
            if not current_file:
                continue
            current_hunk = values
        elif state == 'file':
            rejects += closefile()
            afile, bfile, first_hunk = values
            try:
                if sourcefile:
                    current_file = patchfile(ui, sourcefile)
                else:
                    current_file, missing = selectfile(afile, bfile, first_hunk,
                                            strip, reverse)
                    current_file = patchfile(ui, current_file, missing)
            except PatchError, err:
                ui.warn(str(err) + '\n')
                current_file, current_hunk = None, None
                rejects += 1
                continue
        elif state == 'git':
            gitpatches = values
            for gp in gitpatches:
                if gp.op in ('COPY', 'RENAME'):
                    copyfile(gp.oldpath, gp.path)
                changed[gp.path] = (gp.op, gp)
            raise util.Abort(_('unsupported parser state: %s') % state)

    rejects += closefile()

    if updatedir and gitpatches:
        ignoreblanklines=get('ignore_blank_lines', 'ignoreblanklines'),
        context=get('unified'))
            flags = ''
            if gp.mode & 0100:
                flags = 'x'
            elif gp.mode & 020000:
                flags = 'l'
                repo.wwrite(gp.path, '', flags)
                util.set_flags(dst, flags)
        copy, diverge = copies.copies(repo, ctx1, ctx2, repo.changectx(nullid))
        for k, v in copy.items():
            copy[v] = k
        a, b = f, f
                if f in copy:
                    a = copy[f]
                # have we already reported a copy above?
                if f in copy and copy[f] in added and copy[copy[f]] == f:
                                    a, b, r, opts=opts)
            for line in patchlines:
                p.tochild.write(line + "\n")