from i18n import _
import base85, cmdutil, mdiff, util, context, revlog
import cStringIO, email.Parser, os, popen2, re, sha
import sys, tempfile, zlib
    patch can be a normal patch or contained in an email message.
    return tuple (filename, message, user, date, node, p1, p2).
    Any item in the returned tuple can be None. If filename is None,
    fileobj did not contain a patch. Caller must unlink filename when done.'''
        nodeid = None
        branch = None
        parents = []
            if message.startswith('[PATCH'):
                pend = message.find(']')
                if pend >= 0:
                    message = message[pend+1:].lstrip()
                hgpatch = False
                ignoretext = False

                        elif line.startswith("# Branch "):
                            branch = line[9:]
                        elif line.startswith("# Node ID "):
                            nodeid = line[10:]
                        elif line.startswith("# Parent "):
                            parents.append(line[10:])
                    elif line == '---' and 'git-send-email' in msg['X-Mailer']:
                        ignoretext = True
                    if not line.startswith('# ') and not ignoretext:
        return None, message, user, date, branch, None, None, None
    p1 = parents and parents.pop(0) or None
    p2 = parents and parents.pop(0) or None
    return tmpname, message, user, date, branch, nodeid, p1, p2
        patcher = ui.config('ui', 'patch')
        if not patcher:
            patcher = util.find_exe('gpatch') or util.find_exe('patch')
            # Try to be smart only if patch call was not supplied
            if util.needbinarypatch():
                args.append('--binary')

        if not patcher:
            raise util.Abort(_('no patch command found in hgrc or PATH'))

        cfiles = [util.pathto(repo.root, cwd, f) for f in patches.keys()]
                repo.wwrite(gp.path, '', x and 'x' or '')
            else:
                util.set_exec(dst, x)
    tohash = gitindex(to)
    tnhash = gitindex(tn)
    if tohash == tnhash:
        return ""
    # TODO: deltas
    ret = ['index %s..%s\nGIT binary patch\nliteral %s\n' %
           (tohash, tnhash, len(tn))]
    for l in chunk(zlib.compress(tn)):
        ret.append(fmtline(l))
    ret.append('\n')
    return ''.join(ret)
    ccache = {}
    def getctx(r):
        if r not in ccache:
            ccache[r] = context.changectx(repo, r)
        return ccache[r]

    flcache = {}
    def getfilectx(f, ctx):
        flctx = ctx.filectx(f, filelog=flcache.get(f))
        if f not in flcache:
            flcache[f] = flctx._filelog
        return flctx
    ctx1 = context.changectx(repo, node1)
    # force manifest reading
    man1 = ctx1.manifest()
    date1 = util.datestr(ctx1.date())
    if node2:
        ctx2 = context.changectx(repo, node2)
        execf2 = ctx2.manifest().execf
    else:
        ctx2 = context.workingctx(repo)
        execf2 = util.execfunc(repo.root, None)
        if execf2 is None:
            execf2 = ctx2.parents()[0].manifest().copy().execf

    # returns False if there was no rename between ctx1 and ctx2
    # returns None if the file was created between ctx1 and ctx2
    # returns the (file, node) present in ctx1 that was renamed to f in ctx2
    def renamed(f):
        startrev = ctx1.rev()
        c = ctx2
        crev = c.rev()
        if crev is None:
            crev = repo.changelog.count()
        while crev > startrev:
            if f in c.files():
                    src = getfilectx(f, c).renamed()
                except revlog.LookupError:
            crev = c.parents()[0].rev()
            # try to reuse
            c = getctx(crev)
        if f not in man1:
        return f
        srcs = [x[1] for x in copied.items()]

        if f in man1:
            to = getfilectx(f, ctx1).data()
            tn = getfilectx(f, ctx2).data()
                mode = gitmode(execf2(f))
                    a = copied[f]
                    omode = gitmode(man1.execf(a))
                    to = getfilectx(a, ctx1).data()
                if util.binary(tn):
                    dodiff = 'binary'
                    mode = gitmode(man1.execf(f))
                omode = gitmode(man1.execf(f))
                nmode = gitmode(execf2(f))
        if dodiff:
            if dodiff == 'binary':
                text = b85diff(fp, to, tn)
            else:
                text = mdiff.unidiff(to, date1,
                                    # ctx2 date may be dynamic
                                    tn, util.datestr(ctx2.date()),
                                    f, r, opts=opts)
    revwidth = max([len(str(rev)) for rev in revs])
    def single(rev, seqno, fp):
        ctx = repo.changectx(rev)
        node = ctx.node()
        parents = [p.node() for p in ctx.parents() if p]
        branch = ctx.branch()
        if fp != sys.stdout and hasattr(fp, 'name'):
        fp.write("# User %s\n" % ctx.user())
        fp.write("# Date %d %d\n" % ctx.date())
        if branch and (branch != 'default'):
            fp.write("# Branch %s\n" % branch)
        fp.write(ctx.description().rstrip())
    for seqno, rev in enumerate(revs):
        single(rev, seqno+1, fp)
    if not util.find_exe('diffstat'):
        return