import base85, cmdutil, mdiff, util, context, revlog, diffhelpers
    def __init__(self, desc, num, lr, context, gitpatch=None):
        self.gitpatch = gitpatch
        create = self.gitpatch is None or self.gitpatch.op == 'ADD'
        return self.starta == 0 and self.lena == 0 and create
        remove = self.gitpatch is None or self.gitpatch.op == 'DELETE'
        return self.startb == 0 and self.lenb == 0 and remove
        return path[i:].rstrip()
    afile = pathstrip(afile_orig, strip)
    bfile = pathstrip(bfile_orig, strip)
            fname = (afile in bfile) and afile or bfile
            fname = (afile in bfile) and afile or bfile
                current_hunk = hunk(x, hunknum + 1, lr, context, gpatch)
    # returns False if there was no rename between ctx1 and ctx2
    # returns None if the file was created between ctx1 and ctx2
    # returns the (file, node) present in ctx1 that was renamed to f in ctx2
    # This will only really work if c1 is the Nth 1st parent of c2.
    def renamed(c1, c2, man, f):
        startrev = c1.rev()
        c = c2
        crev = c.rev()
        if crev is None:
            crev = repo.changelog.count()
        orig = f
        files = (f,)
        while crev > startrev:
            if f in files:
                try:
                    src = getfilectx(f, c).renamed()
                except revlog.LookupError:
                    return None
                if src:
                    f = src[0]
            crev = c.parents()[0].rev()
            # try to reuse
            c = getctx(crev)
            files = c.files()
        if f not in man:
            return None
        if f == orig:
            return False
        return f

        copied = {}
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
            if src:
                copied[f] = src
        if ctx1 == c2:
            # invert the copied dict
            copied = dict([(v, k) for (k, v) in copied.iteritems()])
        # If we've renamed file foo to bar (copied['bar'] = 'foo'),
        # avoid showing a diff for foo if we're going to show
        # the rename to bar.
        srcs = [x[1] for x in copied.iteritems() if x[0] in added]
                if f in copied:
                    a = copied[f]
                if f in srcs: