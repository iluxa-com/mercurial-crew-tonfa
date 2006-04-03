# queue.py - patch queues for mercurial
#
# Copyright 2005 Chris Mason <mason@suse.com>
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.

from mercurial.demandload import *
demandload(globals(), "os sys re struct traceback errno bz2")
from mercurial.i18n import gettext as _
from mercurial import ui, hg, revlog, commands, util

versionstr = "0.45"

repomap = {}

class queue:
    def __init__(self, ui, path, patchdir=None):
        self.basepath = path
        if patchdir:
            self.path = patchdir
        else:
            self.path = os.path.join(path, "patches")
        self.opener = util.opener(self.path)
        self.ui = ui
        self.applied = []
        self.full_series = []
        self.applied_dirty = 0
        self.series_dirty = 0
        self.series_path = "series"
        self.status_path = "status"

        if os.path.exists(os.path.join(self.path, self.series_path)):
            self.full_series = self.opener(self.series_path).read().splitlines()
        self.read_series(self.full_series)

        if os.path.exists(os.path.join(self.path, self.status_path)):
            self.applied = self.opener(self.status_path).read().splitlines()

    def find_series(self, patch):
        pre = re.compile("(\s*)([^#]+)")
        index = 0
        for l in self.full_series:
            m = pre.match(l)
            if m:
                s = m.group(2)
                s = s.rstrip()
                if s == patch:
                    return index
            index += 1
        return None

    def read_series(self, list):
        def matcher(list):
            pre = re.compile("(\s*)([^#]+)")
            for l in list:
                m = pre.match(l)
                if m:
                    s = m.group(2)
                    s = s.rstrip()
                    if len(s) > 0:
                        yield s
        self.series = []
        self.series = [ x for x in matcher(list) ]

    def save_dirty(self):
        if self.applied_dirty:
            if len(self.applied) > 0:
                nl = "\n"
            else:
                nl = ""
            f = self.opener(self.status_path, "w")
            f.write("\n".join(self.applied) + nl)
        if self.series_dirty:
            if len(self.full_series) > 0:
                nl = "\n"
            else:
                nl = ""
            f = self.opener(self.series_path, "w")
            f.write("\n".join(self.full_series) + nl)

    def readheaders(self, patch):
        def eatdiff(lines):
            while lines:
                l = lines[-1]
                if (l.startswith("diff -") or
                    l.startswith("Index:") or
                    l.startswith("===========")):
                    del lines[-1]
                else:
                    break
        def eatempty(lines):
            while lines:
                l = lines[-1]
                if re.match('\s*$', l):
                    del lines[-1]
                else:
                    break

        pf = os.path.join(self.path, patch)
        message = []
        comments = []
        user = None
        format = None
        subject = None
        diffstart = 0

        for line in file(pf):
            line = line.rstrip()
            if diffstart:
                if line.startswith('+++ '):
                    diffstart = 2
                break
            if line.startswith("--- "):
                diffstart = 1
                continue
            elif format == "hgpatch":
                # parse values when importing the result of an hg export
                if line.startswith("# User "):
                    user = line[7:]
                elif not line.startswith("# ") and line:
                    message.append(line)
                    format = None
            elif line == '# HG changeset patch':
                format = "hgpatch"
            elif (format != "tagdone" and (line.startswith("Subject: ") or
                                           line.startswith("subject: "))):
                subject = line[9:]
                format = "tag"
            elif (format != "tagdone" and (line.startswith("From: ") or
                                           line.startswith("from: "))):
                user = line[6:]
                format = "tag"
            elif format == "tag" and line == "":
                # when looking for tags (subject: from: etc) they
                # end once you find a blank line in the source
                format = "tagdone"
            else:
                message.append(line)
            comments.append(line)

        eatdiff(message)
        eatdiff(comments)
        eatempty(message)
        eatempty(comments)

        # make sure message isn't empty
        if format and format.startswith("tag") and subject:
            message.insert(0, "")
            message.insert(0, subject)
        return (message, comments, user, diffstart > 1)

    def mergeone(self, repo, mergeq, head, patch, rev, wlock):
        # first try just applying the patch
        (err, n) = self.apply(repo, [ patch ], update_status=False,
                              strict=True, merge=rev, wlock=wlock)

        if err == 0:
            return (err, n)

        if n is None:
            self.ui.warn("apply failed for patch %s\n" % patch)
            sys.exit(1)

        self.ui.warn("patch didn't work out, merging %s\n" % patch)

        # apply failed, strip away that rev and merge.
        repo.update(head, allow=False, force=True, wlock=wlock)
        self.strip(repo, n, update=False, backup='strip', wlock=wlock)

        c = repo.changelog.read(rev)
        ret = repo.update(rev, allow=True, wlock=wlock)
        if ret:
            self.ui.warn("update returned %d\n" % ret)
            sys.exit(1)
        n = repo.commit(None, c[4], c[1], force=1, wlock=wlock)
        if n == None:
            self.ui.warn("repo commit failed\n")
            sys.exit(1)
        try:
            message, comments, user, patchfound = mergeq.readheaders(patch)
        except:
            self.ui.warn("Unable to read %s\n" % patch)
            sys.exit(1)

        patchf = self.opener(patch, "w")
        if comments:
            comments = "\n".join(comments) + '\n\n'
            patchf.write(comments)
        commands.dodiff(patchf, self.ui, repo, head, n)
        patchf.close()
        return (0, n)

    def qparents(self, repo, rev=None):
        if rev is None:
            (p1, p2) = repo.dirstate.parents()
            if p2 == revlog.nullid:
                return p1
            if len(self.applied) == 0:
                return None
            (top, patch) = self.applied[-1].split(':')
            top = revlog.bin(top)
            return top
        pp = repo.changelog.parents(rev)
        if pp[1] != revlog.nullid:
            arevs = [ x.split(':')[0] for x in self.applied ]
            p0 = revlog.hex(pp[0])
            p1 = revlog.hex(pp[1])
            if p0 in arevs:
                return pp[0]
            if p1 in arevs:
                return pp[1]
            return None
        return pp[0]

    def mergepatch(self, repo, mergeq, series, wlock):
        if len(self.applied) == 0:
            # each of the patches merged in will have two parents.  This
            # can confuse the qrefresh, qdiff, and strip code because it
            # needs to know which parent is actually in the patch queue.
            # so, we insert a merge marker with only one parent.  This way
            # the first patch in the queue is never a merge patch
            #
            pname = ".hg.patches.merge.marker"
            n = repo.commit(None, '[mq]: merge marker', user=None, force=1,
                            wlock=wlock)
            self.applied.append(revlog.hex(n) + ":" + pname)
            self.applied_dirty = 1

        head = self.qparents(repo)

        for patch in series:
            patch = mergeq.lookup(patch)
            if not patch:
                self.ui.warn("patch %s does not exist\n" % patch)
                return (1, None)

            info = mergeq.isapplied(patch)
            if not info:
                self.ui.warn("patch %s is not applied\n" % patch)
                return (1, None)
            rev = revlog.bin(info[1])
            (err, head) = self.mergeone(repo, mergeq, head, patch, rev, wlock)
            if head:
                self.applied.append(revlog.hex(head) + ":" + patch)
                self.applied_dirty = 1
            if err:
                return (err, head)
        return (0, head)

    def apply(self, repo, series, list=False, update_status=True,
              strict=False, patchdir=None, merge=None, wlock=None):
        # TODO unify with commands.py
        if not patchdir:
            patchdir = self.path
        pwd = os.getcwd()
        os.chdir(repo.root)
        err = 0
        if not wlock:
            wlock = repo.wlock()
        lock = repo.lock()
        tr = repo.transaction()
        n = None
        for patch in series:
            self.ui.warn("applying %s\n" % patch)
            pf = os.path.join(patchdir, patch)

            try:
                message, comments, user, patchfound = self.readheaders(patch)
            except:
                self.ui.warn("Unable to read %s\n" % pf)
                err = 1
                break

            if not message:
                message = "imported patch %s\n" % patch
            else:
                if list:
                    message.append("\nimported patch %s" % patch)
                message = '\n'.join(message)

            try:
                f = os.popen("patch -p1 --no-backup-if-mismatch < '%s'" % (pf))
            except:
                self.ui.warn("patch failed, unable to continue (try -v)\n")
                err = 1
                break
            files = []
            fuzz = False
            for l in f:
                l = l.rstrip('\r\n');
                if self.ui.verbose:
                    self.ui.warn(l + "\n")
                if l[:14] == 'patching file ':
                    pf = os.path.normpath(l[14:])
                    # when patch finds a space in the file name, it puts
                    # single quotes around the filename.  strip them off
                    if pf[0] == "'" and pf[-1] == "'":
                        pf = pf[1:-1]
                    if pf not in files:
                        files.append(pf)
                    printed_file = False
                    file_str = l
                elif l.find('with fuzz') >= 0:
                    if not printed_file:
                        self.ui.warn(file_str + '\n')
                        printed_file = True
                    self.ui.warn(l + '\n')
                    fuzz = True
                elif l.find('saving rejects to file') >= 0:
                    self.ui.warn(l + '\n')
                elif l.find('FAILED') >= 0:
                    if not printed_file:
                        self.ui.warn(file_str + '\n')
                        printed_file = True
                    self.ui.warn(l + '\n')
            patcherr = f.close()

            if merge and len(files) > 0:
                # Mark as merged and update dirstate parent info
                repo.dirstate.update(repo.dirstate.filterfiles(files), 'm')
                p1, p2 = repo.dirstate.parents()
                repo.dirstate.setparents(p1, merge)
            if len(files) > 0:
                commands.addremove_lock(self.ui, repo, files,
                                        opts={}, wlock=wlock)
            n = repo.commit(files, message, user, force=1, lock=lock,
                            wlock=wlock)

            if n == None:
                self.ui.warn("repo commit failed\n")
                sys.exit(1)

            if update_status:
                self.applied.append(revlog.hex(n) + ":" + patch)

            if patcherr:
                if not patchfound:
                    self.ui.warn("patch %s is empty\n" % patch)
                    err = 0
                else:
                    self.ui.warn("patch failed, rejects left in working dir\n")
                    err = 1
                break

            if fuzz and strict:
                self.ui.warn("fuzz found when applying patch, stopping\n")
                err = 1
                break
        tr.close()
        os.chdir(pwd)
        return (err, n)

    def delete(self, repo, patch):
        patch = self.lookup(patch)
        info = self.isapplied(patch)
        if info:
            self.ui.warn("cannot delete applied patch %s\n" % patch)
            sys.exit(1)
        if patch not in self.series:
            self.ui.warn("patch %s not in series file\n" % patch)
            sys.exit(1)
        i = self.find_series(patch)
        del self.full_series[i]
        self.read_series(self.full_series)
        self.series_dirty = 1

    def check_toppatch(self, repo):
        if len(self.applied) > 0:
            (top, patch) = self.applied[-1].split(':')
            top = revlog.bin(top)
            pp = repo.dirstate.parents()
            if top not in pp:
                self.ui.warn("queue top not at dirstate parents. top %s dirstate %s %s\n" %( revlog.short(top), revlog.short(pp[0]), revlog.short(pp[1])))
                sys.exit(1)
            return top
        return None
    def check_localchanges(self, repo):
        (c, a, r, d, u) = repo.changes(None, None)
        if c or a or d or r:
            self.ui.write("Local changes found, refresh first\n")
            sys.exit(1)
    def new(self, repo, patch, msg=None, force=None):
        if not force:
            self.check_localchanges(repo)
        self.check_toppatch(repo)
        wlock = repo.wlock()
        insert = self.series_end()
        if msg:
            n = repo.commit([], "[mq]: %s" % msg, force=True, wlock=wlock)
        else:
            n = repo.commit([],
                            "New patch: %s" % patch, force=True, wlock=wlock)
        if n == None:
            self.ui.warn("repo commit failed\n")
            sys.exit(1)
        self.full_series[insert:insert] = [patch]
        self.applied.append(revlog.hex(n) + ":" + patch)
        self.read_series(self.full_series)
        self.series_dirty = 1
        self.applied_dirty = 1
        p = self.opener(patch, "w")
        if msg:
            msg = msg + "\n"
            p.write(msg)
        p.close()
        wlock = None
        r = self.qrepo()
        if r: r.add([patch])

    def strip(self, repo, rev, update=True, backup="all", wlock=None):
        def limitheads(chlog, stop):
            """return the list of all nodes that have no children"""
            p = {}
            h = []
            stoprev = 0
            if stop in chlog.nodemap:
                stoprev = chlog.rev(stop)

            for r in range(chlog.count() - 1, -1, -1):
                n = chlog.node(r)
                if n not in p:
                    h.append(n)
                if n == stop:
                    break
                if r < stoprev:
                    break
                for pn in chlog.parents(n):
                    p[pn] = 1
            return h

        def bundle(cg):
            backupdir = repo.join("strip-backup")
            if not os.path.isdir(backupdir):
                os.mkdir(backupdir)
            name = os.path.join(backupdir, "%s" % revlog.short(rev))
            name = savename(name)
            self.ui.warn("saving bundle to %s\n" % name)
            # TODO, exclusive open
            f = open(name, "wb")
            try:
                f.write("HG10")
                z = bz2.BZ2Compressor(9)
                while 1:
                    chunk = cg.read(4096)
                    if not chunk:
                        break
                    f.write(z.compress(chunk))
                f.write(z.flush())
            except:
                os.unlink(name)
                raise
            f.close()
            return name

        def stripall(rev, revnum):
            cl = repo.changelog
            c = cl.read(rev)
            mm = repo.manifest.read(c[0])
            seen = {}

            for x in xrange(revnum, cl.count()):
                c = cl.read(cl.node(x))
                for f in c[3]:
                    if f in seen:
                        continue
                    seen[f] = 1
                    if f in mm:
                        filerev = mm[f]
                    else:
                        filerev = 0
                    seen[f] = filerev
            # we go in two steps here so the strip loop happens in a
            # sensible order.  When stripping many files, this helps keep
            # our disk access patterns under control.
            list = seen.keys()
            list.sort()
            for f in list:
                ff = repo.file(f)
                filerev = seen[f]
                if filerev != 0:
                    if filerev in ff.nodemap:
                        filerev = ff.rev(filerev)
                    else:
                        filerev = 0
                ff.strip(filerev, revnum)

        if not wlock:
            wlock = repo.wlock()
        lock = repo.lock()
        chlog = repo.changelog
        # TODO delete the undo files, and handle undo of merge sets
        pp = chlog.parents(rev)
        revnum = chlog.rev(rev)

        if update:
            urev = self.qparents(repo, rev)
            repo.update(urev, allow=False, force=True, wlock=wlock)
            repo.dirstate.write()

        # save is a list of all the branches we are truncating away
        # that we actually want to keep.  changegroup will be used
        # to preserve them and add them back after the truncate
        saveheads = []
        savebases = {}

        tip = chlog.tip()
        heads = limitheads(chlog, rev)
        seen = {}

        # search through all the heads, finding those where the revision
        # we want to strip away is an ancestor.  Also look for merges
        # that might be turned into new heads by the strip.
        while heads:
            h = heads.pop()
            n = h
            while True:
                seen[n] = 1
                pp = chlog.parents(n)
                if pp[1] != revlog.nullid and chlog.rev(pp[1]) > revnum:
                    if pp[1] not in seen:
                        heads.append(pp[1])
                if pp[0] == revlog.nullid:
                    break
                if chlog.rev(pp[0]) < revnum:
                    break
                n = pp[0]
                if n == rev:
                    break
            r = chlog.reachable(h, rev)
            if rev not in r:
                saveheads.append(h)
                for x in r:
                    if chlog.rev(x) > revnum:
                        savebases[x] = 1

        # create a changegroup for all the branches we need to keep
        if backup is "all":
            backupch = repo.changegroupsubset([rev], chlog.heads(), 'strip')
            bundle(backupch)
        if saveheads:
            backupch = repo.changegroupsubset(savebases.keys(), saveheads, 'strip')
            chgrpfile = bundle(backupch)

        stripall(rev, revnum)

        change = chlog.read(rev)
        repo.manifest.strip(repo.manifest.rev(change[0]), revnum)
        chlog.strip(revnum, revnum)
        if saveheads:
            self.ui.status("adding branch\n")
            commands.unbundle(self.ui, repo, chgrpfile, update=False)
            if backup is not "strip":
                os.unlink(chgrpfile)

    def isapplied(self, patch):
        """returns (index, rev, patch)"""
        for i in xrange(len(self.applied)):
            p = self.applied[i]
            a = p.split(':')
            if a[1] == patch:
                return (i, a[0], a[1])
        return None

    def lookup(self, patch):
        if patch == None:
            return None
        if patch in self.series:
            return patch
        if not os.path.isfile(os.path.join(self.path, patch)):
            try:
                sno = int(patch)
            except(ValueError, OverflowError):
                self.ui.warn("patch %s not in series\n" % patch)
                sys.exit(1)
            if sno >= len(self.series):
                self.ui.warn("patch number %d is out of range\n" % sno)
                sys.exit(1)
            patch = self.series[sno]
        else:
            self.ui.warn("patch %s not in series\n" % patch)
            sys.exit(1)
        return patch

    def push(self, repo, patch=None, force=False, list=False,
             mergeq=None, wlock=None):
        if not wlock:
            wlock = repo.wlock()
        patch = self.lookup(patch)
        if patch and self.isapplied(patch):
            self.ui.warn("patch %s is already applied\n" % patch)
            sys.exit(1)
        if self.series_end() == len(self.series):
            self.ui.warn("File series fully applied\n")
            sys.exit(1)
        if not force:
            self.check_localchanges(repo)

        self.applied_dirty = 1;
        start = self.series_end()
        if start > 0:
            self.check_toppatch(repo)
        if not patch:
            patch = self.series[start]
            end = start + 1
        else:
            end = self.series.index(patch, start) + 1
        s = self.series[start:end]
        if mergeq:
            ret = self.mergepatch(repo, mergeq, s, wlock)
        else:
            ret = self.apply(repo, s, list, wlock=wlock)
        top = self.applied[-1].split(':')[1]
        if ret[0]:
            self.ui.write("Errors during apply, please fix and refresh %s\n" %
                          top)
        else:
            self.ui.write("Now at: %s\n" % top)
        return ret[0]

    def pop(self, repo, patch=None, force=False, update=True, wlock=None):
        def getfile(f, rev):
            t = repo.file(f).read(rev)
            try:
                repo.wfile(f, "w").write(t)
            except IOError:
                os.makedirs(os.path.dirname(repo.wjoin(f)))
                repo.wfile(f, "w").write(t)

        if not wlock:
            wlock = repo.wlock()
        if patch:
            # index, rev, patch
            info = self.isapplied(patch)
            if not info:
                patch = self.lookup(patch)
            info = self.isapplied(patch)
            if not info:
                self.ui.warn("patch %s is not applied\n" % patch)
                sys.exit(1)
        if len(self.applied) == 0:
            self.ui.warn("No patches applied\n")
            sys.exit(1)

        if not update:
            parents = repo.dirstate.parents()
            rr = [ revlog.bin(x.split(':')[0]) for x in self.applied ]
            for p in parents:
                if p in rr:
                    self.ui.warn("qpop: forcing dirstate update\n")
                    update = True

        if not force and update:
            self.check_localchanges(repo)

        self.applied_dirty = 1;
        end = len(self.applied)
        if not patch:
            info = [len(self.applied) - 1] + self.applied[-1].split(':')
        start = info[0]
        rev = revlog.bin(info[1])

        # we know there are no local changes, so we can make a simplified
        # form of hg.update.
        if update:
            top = self.check_toppatch(repo)
            qp = self.qparents(repo, rev)
            changes = repo.changelog.read(qp)
            mf1 = repo.manifest.readflags(changes[0])
            mmap = repo.manifest.read(changes[0])
            (c, a, r, d, u) = repo.changes(qp, top)
            if d:
                raise util.Abort("deletions found between repo revs")
            for f in c:
                getfile(f, mmap[f])
            for f in r:
                getfile(f, mmap[f])
                util.set_exec(repo.wjoin(f), mf1[f])
            repo.dirstate.update(c + r, 'n')
            for f in a:
                try: os.unlink(repo.wjoin(f))
                except: raise
                try: os.removedirs(os.path.dirname(repo.wjoin(f)))
                except: pass
            if a:
                repo.dirstate.forget(a)
            repo.dirstate.setparents(qp, revlog.nullid)
        self.strip(repo, rev, update=False, backup='strip', wlock=wlock)
        del self.applied[start:end]
        if len(self.applied):
            self.ui.write("Now at: %s\n" % self.applied[-1].split(':')[1])
        else:
            self.ui.write("Patch queue now empty\n")

    def diff(self, repo, files):
        top = self.check_toppatch(repo)
        if not top:
            self.ui.write("No patches applied\n")
            return
        qp = self.qparents(repo, top)
        commands.dodiff(sys.stdout, self.ui, repo, qp, None, files)

    def refresh(self, repo, short=False):
        if len(self.applied) == 0:
            self.ui.write("No patches applied\n")
            return
        wlock = repo.wlock()
        self.check_toppatch(repo)
        qp = self.qparents(repo)
        (top, patch) = self.applied[-1].split(':')
        top = revlog.bin(top)
        cparents = repo.changelog.parents(top)
        patchparent = self.qparents(repo, top)
        message, comments, user, patchfound = self.readheaders(patch)

        patchf = self.opener(patch, "w")
        if comments:
            comments = "\n".join(comments) + '\n\n'
            patchf.write(comments)

        tip = repo.changelog.tip()
        if top == tip:
            # if the top of our patch queue is also the tip, there is an
            # optimization here.  We update the dirstate in place and strip
            # off the tip commit.  Then just commit the current directory
            # tree.  We can also send repo.commit the list of files
            # changed to speed up the diff
            #
            # in short mode, we only diff the files included in the
            # patch already
            #
            # this should really read:
            #(cc, dd, aa, aa2, uu) = repo.changes(tip, patchparent)
            # but we do it backwards to take advantage of manifest/chlog
            # caching against the next repo.changes call
            #
            (cc, aa, dd, aa2, uu) = repo.changes(patchparent, tip)
            if short:
                filelist = cc + aa + dd
            else:
                filelist = None
            (c, a, r, d, u) = repo.changes(None, None, filelist)

            # we might end up with files that were added between tip and
            # the dirstate parent, but then changed in the local dirstate.
            # in this case, we want them to only show up in the added section
            for x in c:
                if x not in aa:
                    cc.append(x)
            # we might end up with files added by the local dirstate that
            # were deleted by the patch.  In this case, they should only
            # show up in the changed section.
            for x in a:
                if x in dd:
                    del dd[dd.index(x)]
                    cc.append(x)
                else:
                    aa.append(x)
            # make sure any files deleted in the local dirstate
            # are not in the add or change column of the patch
            forget = []
            for x in d + r:
                if x in aa:
                    del aa[aa.index(x)]
                    forget.append(x)
                    continue
                elif x in cc:
                    del cc[cc.index(x)]
                dd.append(x)

            c = list(util.unique(cc))
            r = list(util.unique(dd))
            a = list(util.unique(aa))
            filelist = list(util.unique(c + r + a ))
            commands.dodiff(patchf, self.ui, repo, patchparent, None,
                            filelist, changes=(c, a, r, [], u))
            patchf.close()

            changes = repo.changelog.read(tip)
            repo.dirstate.setparents(*cparents)
            repo.dirstate.update(a, 'a')
            repo.dirstate.update(r, 'r')
            repo.dirstate.update(c, 'n')
            repo.dirstate.forget(forget)

            if not message:
                message = "patch queue: %s\n" % patch
            else:
                message = "\n".join(message)
            self.strip(repo, top, update=False, backup='strip', wlock=wlock)
            n = repo.commit(filelist, message, changes[1], force=1, wlock=wlock)
            self.applied[-1] = revlog.hex(n) + ':' + patch
            self.applied_dirty = 1
        else:
            commands.dodiff(patchf, self.ui, repo, patchparent, None)
            patchf.close()
            self.pop(repo, force=True, wlock=wlock)
            self.push(repo, force=True, wlock=wlock)

    def init(self, repo, create=False):
        if os.path.isdir(self.path):
            raise util.Abort("patch queue directory already exists")
        os.mkdir(self.path)
        if create:
            return self.qrepo(create=True)

    def unapplied(self, repo, patch=None):
        if patch and patch not in self.series:
            self.ui.warn("%s not in the series file\n" % patch)
            sys.exit(1)
        if not patch:
            start = self.series_end()
        else:
            start = self.series.index(patch) + 1
        for p in self.series[start:]:
            self.ui.write("%s\n" % p)

    def qseries(self, repo, missing=None):
        start = self.series_end()
        if not missing:
            for p in self.series[:start]:
                if self.ui.verbose:
                    self.ui.write("%d A " % self.series.index(p))
                self.ui.write("%s\n" % p)
            for p in self.series[start:]:
                if self.ui.verbose:
                    self.ui.write("%d U " % self.series.index(p))
                self.ui.write("%s\n" %  p)
        else:
            list = []
            for root, dirs, files in os.walk(self.path):
                d = root[len(self.path) + 1:]
                for f in files:
                    fl = os.path.join(d, f)
                    if (fl not in self.series and
                        fl not in (self.status_path, self.series_path)
                        and not fl.startswith('.')):
                        list.append(fl)
            list.sort()
            if list:
                for x in list:
                    if self.ui.verbose:
                        self.ui.write("D ")
                    self.ui.write("%s\n" % x)

    def issaveline(self, l):
        name = l.split(':')[1]
        if name == '.hg.patches.save.line':
            return True

    def qrepo(self, create=False):
        if create or os.path.isdir(os.path.join(self.path, ".hg")):
            return hg.repository(self.ui, path=self.path, create=create)

    def restore(self, repo, rev, delete=None, qupdate=None):
        c = repo.changelog.read(rev)
        desc = c[4].strip()
        lines = desc.splitlines()
        i = 0
        datastart = None
        series = []
        applied = []
        qpp = None
        for i in xrange(0, len(lines)):
            if lines[i] == 'Patch Data:':
                datastart = i + 1
            elif lines[i].startswith('Dirstate:'):
                l = lines[i].rstrip()
                l = l[10:].split(' ')
                qpp = [ hg.bin(x) for x in l ]
            elif datastart != None:
                l = lines[i].rstrip()
                index = l.index(':')
                id = l[:index]
                file = l[index + 1:]
                if id:
                    applied.append(l)
                series.append(file)
        if datastart == None:
            self.ui.warn("No saved patch data found\n")
            return 1
        self.ui.warn("restoring status: %s\n" % lines[0])
        self.full_series = series
        self.applied = applied
        self.read_series(self.full_series)
        self.series_dirty = 1
        self.applied_dirty = 1
        heads = repo.changelog.heads()
        if delete:
            if rev not in heads:
                self.ui.warn("save entry has children, leaving it alone\n")
            else:
                self.ui.warn("removing save entry %s\n" % hg.short(rev))
                pp = repo.dirstate.parents()
                if rev in pp:
                    update = True
                else:
                    update = False
                self.strip(repo, rev, update=update, backup='strip')
        if qpp:
            self.ui.warn("saved queue repository parents: %s %s\n" %
                         (hg.short(qpp[0]), hg.short(qpp[1])))
            if qupdate:
                print "queue directory updating"
                r = self.qrepo()
                if not r:
                    self.ui.warn("Unable to load queue repository\n")
                    return 1
                r.update(qpp[0], allow=False, force=True)

    def save(self, repo, msg=None):
        if len(self.applied) == 0:
            self.ui.warn("save: no patches applied, exiting\n")
            return 1
        if self.issaveline(self.applied[-1]):
            self.ui.warn("status is already saved\n")
            return 1

        ar = [ ':' + x for x in self.full_series ]
        if not msg:
            msg = "hg patches saved state"
        else:
            msg = "hg patches: " + msg.rstrip('\r\n')
        r = self.qrepo()
        if r:
            pp = r.dirstate.parents()
            msg += "\nDirstate: %s %s" % (hg.hex(pp[0]), hg.hex(pp[1]))
        msg += "\n\nPatch Data:\n"
        text = msg + "\n".join(self.applied) + '\n' + (ar and "\n".join(ar)
                                                       + '\n' or "")
        n = repo.commit(None, text, user=None, force=1)
        if not n:
            self.ui.warn("repo commit failed\n")
            return 1
        self.applied.append(revlog.hex(n) + ":" + '.hg.patches.save.line')
        self.applied_dirty = 1

    def series_end(self):
        end = 0
        if len(self.applied) > 0:
            (top, p) = self.applied[-1].split(':')
            try:
                end = self.series.index(p)
            except ValueError:
                return 0
            return end + 1
        return end

    def qapplied(self, repo, patch=None):
        if patch and patch not in self.series:
            self.ui.warn("%s not in the series file\n" % patch)
            sys.exit(1)
        if not patch:
            end = len(self.applied)
        else:
            end = self.series.index(patch) + 1
        for x in xrange(end):
            p = self.appliedname(x)
            self.ui.write("%s\n" % p)

    def appliedname(self, index):
        p = self.applied[index]
        if not self.ui.verbose:
            p = p.split(':')[1]
        return p

    def top(self, repo):
        if len(self.applied):
            p = self.appliedname(-1)
            self.ui.write(p + '\n')
        else:
            self.ui.write("No patches applied\n")

    def next(self, repo):
        end = self.series_end()
        if end == len(self.series):
            self.ui.write("All patches applied\n")
        else:
            self.ui.write(self.series[end] + '\n')

    def prev(self, repo):
        if len(self.applied) > 1:
            p = self.appliedname(-2)
            self.ui.write(p + '\n')
        elif len(self.applied) == 1:
            self.ui.write("Only one patch applied\n")
        else:
            self.ui.write("No patches applied\n")

    def qimport(self, repo, files, patch=None, existing=None, force=None):
        if len(files) > 1 and patch:
            self.ui.warn("-n option not valid when importing multiple files\n")
            sys.exit(1)
        i = 0
        for filename in files:
            if existing:
                if not patch:
                    patch = filename
                if not os.path.isfile(os.path.join(self.path, patch)):
                    self.ui.warn("patch %s does not exist\n" % patch)
                    sys.exit(1)
            else:
                try:
                    text = file(filename).read()
                except IOError:
                    self.ui.warn("Unable to read %s\n" % patch)
                    sys.exit(1)
                if not patch:
                    patch = os.path.split(filename)[1]
                if not force and os.path.isfile(os.path.join(self.path, patch)):
                    self.ui.warn("patch %s already exists\n" % patch)
                    sys.exit(1)
                patchf = self.opener(patch, "w")
                patchf.write(text)
            if patch in self.series:
                self.ui.warn("patch %s is already in the series file\n" % patch)
                sys.exit(1)
            index = self.series_end() + i
            self.full_series[index:index] = [patch]
            self.read_series(self.full_series)
            self.ui.warn("adding %s to series file\n" % patch)
            i += 1
            patch = None
        self.series_dirty = 1

def delete(ui, repo, patch, **opts):
    """remove a patch from the series file"""
    q = repomap[repo]
    q.delete(repo, patch)
    q.save_dirty()
    return 0

def applied(ui, repo, patch=None, **opts):
    """print the patches already applied"""
    repomap[repo].qapplied(repo, patch)
    return 0

def unapplied(ui, repo, patch=None, **opts):
    """print the patches not yet applied"""
    repomap[repo].unapplied(repo, patch)
    return 0

def qimport(ui, repo, *filename, **opts):
    """import a patch"""
    q = repomap[repo]
    q.qimport(repo, filename, patch=opts['name'],
              existing=opts['existing'], force=opts['force'])
    q.save_dirty()
    return 0

def init(ui, repo, **opts):
    """init a new queue repository"""
    q = repomap[repo]
    r = q.init(repo, create=opts['create_repo'])
    q.save_dirty()
    if r:
        fp = r.wopener('.hgignore', 'w')
        print >> fp, 'syntax: glob'
        print >> fp, 'status'
        fp.close()
        r.wopener('series', 'w').close()
        r.add(['.hgignore', 'series'])
    return 0

def commit(ui, repo, *pats, **opts):
    q = repomap[repo]
    r = q.qrepo()
    if not r: raise util.Abort('no queue repository')
    commands.commit(r.ui, r, *pats, **opts)

def series(ui, repo, **opts):
    """print the entire series file"""
    repomap[repo].qseries(repo, missing=opts['missing'])
    return 0

def top(ui, repo, **opts):
    """print the name of the current patch"""
    repomap[repo].top(repo)
    return 0

def next(ui, repo, **opts):
    """print the name of the next patch"""
    repomap[repo].next(repo)
    return 0

def prev(ui, repo, **opts):
    """print the name of the previous patch"""
    repomap[repo].prev(repo)
    return 0

def new(ui, repo, patch, **opts):
    """create a new patch"""
    q = repomap[repo]
    q.new(repo, patch, msg=opts['message'], force=opts['force'])
    q.save_dirty()
    return 0

def refresh(ui, repo, **opts):
    """update the current patch"""
    q = repomap[repo]
    q.refresh(repo, short=opts['short'])
    q.save_dirty()
    return 0

def diff(ui, repo, *files, **opts):
    """diff of the current patch"""
    repomap[repo].diff(repo, files)
    return 0

def lastsavename(path):
    (dir, base) = os.path.split(path)
    names = os.listdir(dir)
    namere = re.compile("%s.([0-9]+)" % base)
    max = None
    maxname = None
    for f in names:
        m = namere.match(f)
        if m:
            index = int(m.group(1))
            if max == None or index > max:
                max = index
                maxname = f
    if maxname:
        return (os.path.join(dir, maxname), max)
    return (None, None)

def savename(path):
    (last, index) = lastsavename(path)
    if last is None:
        index = 0
    newpath = path + ".%d" % (index + 1)
    return newpath

def push(ui, repo, patch=None, **opts):
    """push the next patch onto the stack"""
    q = repomap[repo]
    mergeq = None

    if opts['all']:
        patch = q.series[-1]
    if opts['merge']:
        if opts['name']:
            newpath = opts['name']
        else:
            newpath, i = lastsavename(q.path)
        if not newpath:
            ui.warn("no saved queues found, please use -n\n")
            return 1
        mergeq = queue(ui, repo.join(""), newpath)
        ui.warn("merging with queue at: %s\n" % mergeq.path)
    ret = q.push(repo, patch, force=opts['force'], list=opts['list'],
                 mergeq=mergeq)
    q.save_dirty()
    return ret

def pop(ui, repo, patch=None, **opts):
    """pop the current patch off the stack"""
    localupdate = True
    if opts['name']:
        q = queue(ui, repo.join(""), repo.join(opts['name']))
        ui.warn('using patch queue: %s\n' % q.path)
        localupdate = False
    else:
        q = repomap[repo]
    if opts['all'] and len(q.applied) > 0:
        patch = q.applied[0].split(':')[1]
    q.pop(repo, patch, force=opts['force'], update=localupdate)
    q.save_dirty()
    return 0

def restore(ui, repo, rev, **opts):
    """restore the queue state saved by a rev"""
    rev = repo.lookup(rev)
    q = repomap[repo]
    q.restore(repo, rev, delete=opts['delete'],
              qupdate=opts['update'])
    q.save_dirty()
    return 0

def save(ui, repo, **opts):
    """save current queue state"""
    q = repomap[repo]
    ret = q.save(repo, msg=opts['message'])
    if ret:
        return ret
    q.save_dirty()
    if opts['copy']:
        path = q.path
        if opts['name']:
            newpath = os.path.join(q.basepath, opts['name'])
            if os.path.exists(newpath):
                if not os.path.isdir(newpath):
                    ui.warn("destination %s exists and is not a directory\n" %
                            newpath)
                    sys.exit(1)
                if not opts['force']:
                    ui.warn("destination %s exists, use -f to force\n" %
                            newpath)
                    sys.exit(1)
        else:
            newpath = savename(path)
        ui.warn("copy %s to %s\n" % (path, newpath))
        util.copyfiles(path, newpath)
    if opts['empty']:
        try:
            os.unlink(os.path.join(q.path, q.status_path))
        except:
            pass
    return 0

def strip(ui, repo, rev, **opts):
    """strip a revision and all later revs on the same branch"""
    rev = repo.lookup(rev)
    backup = 'all'
    if opts['backup']:
        backup = 'strip'
    elif opts['nobackup']:
        backup = 'none'
    repomap[repo].strip(repo, rev, backup=backup)
    return 0

def version(ui, q=None):
    """print the version number"""
    ui.write("mq version %s\n" % versionstr)
    return 0

def reposetup(ui, repo):
    repomap[repo] = queue(ui, repo.join(""))

cmdtable = {
    "qapplied": (applied, [], 'hg qapplied [patch]'),
    "qcommit|qci":
        (commit,
         [('A', 'addremove', None, _('run addremove during commit')),
          ('I', 'include', [], _('include names matching the given patterns')),
          ('X', 'exclude', [], _('exclude names matching the given patterns')),
          ('m', 'message', '', _('use <text> as commit message')),
          ('l', 'logfile', '', _('read the commit message from <file>')),
          ('d', 'date', '', _('record datecode as commit date')),
          ('u', 'user', '', _('record user as commiter'))],
         'hg qcommit [options] [files]'),
    "^qdiff": (diff, [], 'hg qdiff [files]'),
    "qdelete": (delete, [], 'hg qdelete [patch]'),
    "^qimport":
        (qimport,
         [('e', 'existing', None, 'import file in patch dir'),
          ('n', 'name', '', 'patch file name'),
          ('f', 'force', None, 'overwrite existing files')],
         'hg qimport'),
    "^qinit":
        (init,
         [('c', 'create-repo', None, 'create patch repository')],
         'hg [-c] qinit'),
    "qnew":
        (new,
         [('m', 'message', '', 'commit message'),
          ('f', 'force', None, 'force')],
         'hg qnew [-m message ] patch'),
    "qnext": (next, [], 'hg qnext'),
    "qprev": (prev, [], 'hg qprev'),
    "^qpop":
        (pop,
         [('a', 'all', None, 'pop all patches'),
          ('n', 'name', '', 'queue name to pop'),
          ('f', 'force', None, 'forget any local changes')],
         'hg qpop [options] [patch/index]'),
    "^qpush":
        (push,
         [('f', 'force', None, 'apply if the patch has rejects'),
          ('l', 'list', None, 'list patch name in commit text'),
          ('a', 'all', None, 'apply all patches'),
          ('m', 'merge', None, 'merge from another queue'),
          ('n', 'name', '', 'merge queue name')],
         'hg qpush [options] [patch/index]'),
    "^qrefresh":
        (refresh,
         [('s', 'short', None, 'short refresh')],
         'hg qrefresh'),
    "qrestore":
        (restore,
         [('d', 'delete', None, 'delete save entry'),
          ('u', 'update', None, 'update queue working dir')],
         'hg qrestore rev'),
    "qsave":
        (save,
         [('m', 'message', '', 'commit message'),
          ('c', 'copy', None, 'copy patch directory'),
          ('n', 'name', '', 'copy directory name'),
          ('e', 'empty', None, 'clear queue status file'),
          ('f', 'force', None, 'force copy')],
         'hg qsave'),
    "qseries":
        (series,
         [('m', 'missing', None, 'print patches not in series')],
         'hg qseries'),
    "^strip":
        (strip,
         [('f', 'force', None, 'force multi-head removal'),
          ('b', 'backup', None, 'bundle unrelated changesets'),
          ('n', 'nobackup', None, 'no backups')],
         'hg strip rev'),
    "qtop": (top, [], 'hg qtop'),
    "qunapplied": (unapplied, [], 'hg qunapplied [patch]'),
    "qversion": (version, [], 'hg qversion')
}
