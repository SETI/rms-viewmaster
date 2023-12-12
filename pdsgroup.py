################################################################################
# File grouping class. An ordered set of PdsFiles, some of which may be hidden.
# They must share a common parent and anchor. In Viewmaster, they appear on the
# same row of a table, where a row boundaries are identified by transition
# between gray and white.
################################################################################

import os
import pdsfile
import pdsviewable

class PdsGroup(object):
    """PdsGroup defines an ordered list of PdsFiles that are expected to be
    grouped together when displayed. This is most commonly used to show a file
    and its label in the same row within Viewmaster, where row backgrounds
    alternate between gray and white.

    All the members of a PdsGroup must reside within the same directory.

    At any given time, one or more members of the group may be "hidden", in
    which case the default PdsGroup iterator will skip over them.
    """

    def __init__(self, pdsfiles=[], parent=False, anchor=None, hidden=[]):
        """PdsGroup constructor.

        Input:
            pdsfiles        an ordered list of PdsFiles. Can be empty, which
                            means the PdsGroup does not yet have any members.
            parent          the common parent of all the PdsFiles. False to
                            derive this from the pdsfiles. None means that the
                            parent is a merged directory.
            anchor          a string referring to this PdsGroup, which should
                            be unique within the directory. None for default,
                            which is derived from the basename of the first file
                            in the group.
            hidden          a list or set of the logical paths of rows that are
                            to be treated as hidden. Default is an empty list.
        """

        self.parent_pdsf = parent   # False means un-initialized, in which case
                                    # it is derived when self.append is first
                                    # called. None means this is part of a
                                    # merged directory.
        self.anchor = None
        self.rows = []
        self.hidden = set(hidden)

        self._isdir_filled = None
        self._iconset_filled = None
        self._viewset_filled = None
        self._local_viewset_filled = None
        self._all_viewsets_filled = None

        if isinstance(pdsfiles, (list, tuple)):
            for pdsf in pdsfiles:
                self.append(pdsf)
        else:
            self.append(pdsfiles)

    def __len__(self):
        return len(self.rows) - len(self.hidden)

    def __repr__(self):
        if self.rows:
            path = self.rows[0].logical_path

            if len(self.rows) >= 2:
                return f'PdsGroup("{path}",...[{len(self.rows)}])'
            else:
                return f'PdsGroup("{path}")'
        else:
            return f'PdsGroup()'

    def copy(self):
        this = PdsGroup()
        this.parent_pdsf = self.parent_pdsf
        this.anchor = self.anchor
        this.rows = list(self.rows)
        this.hidden = self.hidden.copy()

        this._isdir_filled = self._isdir_filled
        this._iconset_filled = self._iconset_filled
        this._viewset_filled = self._viewset_filled
        this._local_viewset_filled = self._local_viewset_filled
        this._all_viewsets_filled = self._all_viewsets_filled

        return this

    @property
    def parent_logical_path(self):
        """Logical path of the parent."""

        if self.parent_pdsf:
            return self.parent_pdsf.logical_path
        else:
            return ''

    @property
    def isdir(self):
        if self._isdir_filled is None:
            self._isdir_filled = any([p.isdir for p in self.rows])

        return self._isdir_filled

    @property
    def _iconset(self):
        """Internal method to return the PdsViewSet of this object's icon,
        whether it is to be displayed in a closed or open state."""

        if self._iconset_filled:
            return self._iconset_filled[False]

        # Initially, select the most generic icon type
        if self.rows[0].isdir:
            best_type = 'FOLDER'
        elif self.rows[0].islabel:
            best_type = 'LABEL'
        else:
            best_type = 'UNKNOWN'

        best_set = pdsviewable.ICON_SET_BY_TYPE[best_type, False]

        # Improve the icon set if possible
        for pdsf in self.rows:
            try:
                test = pdsviewable.ICON_SET_BY_TYPE[pdsf.icon_type, False]
            except KeyError:        # missing icon_type
                continue

            if test.priority > best_set.priority:
                best_type = pdsf.icon_type
                best_set = pdsviewable.ICON_SET_BY_TYPE[best_type, False]

        # Create the dictionary
        self._iconset_filled = {
            False: best_set,
            True:  pdsviewable.ICON_SET_BY_TYPE[best_type, True]
        }

        return self._iconset_filled[False]

    @property
    def iconset_closed(self):
        """The "closed" or default icon set for this group. Folders typically
        have a different icon when open vs. when closed; for documents, the
        "open" and "closed" icons are usually the same."""

        _ = self._iconset
        return self._iconset_filled[False]

    @property
    def iconset_open(self):
        """The "open" icon set for this group."""

        _ = self._iconset
        return self._iconset_filled[True]

    @property
    def viewset(self):
        """The local PdsViewSet if it exists; otherwise, the first PdsViewSet.
        """

        if self._viewset_filled is None:

            if self.local_viewset:
                self._viewset_filled = self.local_viewset

            else:
                self._viewset_filled = False
                for pdsf in self.rows:
                    if pdsf.viewset:
                        self._viewset_filled = pdsf.viewset
                        break

        return self._viewset_filled

    @property
    def local_viewset(self):
        """The PdsViewSet of this object if it is viewable; False otherwise.
        """

        if self._local_viewset_filled is None:

            viewset = pdsviewable.PdsViewSet()
            for pdsf in self.rows:
                if pdsf.local_viewset:
                    viewset.append(pdsf.local_viewset)

            if len(viewset) == len(self):
                self._local_viewset_filled = viewset
            else:
                self._local_viewset_filled = False

        return self._local_viewset_filled

    @property
    def all_viewsets(self):
        """A dictionary of all the PdsViewSets for this object.
        """

        if self._all_viewsets_filled is None:

            merged_dict = {}
            for pdsf in self.rows:
                for key in pdsf.all_viewsets:
                    if key not in merged_dict:
                        merged_dict[key] = pdsf.all_viewsets[key]

            self._all_viewsets_filled = merged_dict

        return self._all_viewsets_filled

    @property
    def global_anchor(self):
        """A globally unique anchor string for this group."""

        if self.parent_pdsf is False:
            raise ValueError('PdsGroup has not been initialized')

        if self.parent_pdsf is None:        # if a merged directory
            return self.anchor
        else:
            return self.parent_pdsf.global_anchor + '-' + self.anchor

    def sort(self, labels_after=None, dirs_first=None, dirs_last=None,
                   info_first=None):
        """Sort the rows of this group."""

        basename_dict = {pdsf.basename:pdsf for pdsf in self.rows}

        if self.parent_pdsf:
            sorted = self.parent_pdsf.sort_basenames(list(basename_dict.keys()),
                                                labels_after=labels_after,
                                                dirs_first=dirs_first,
                                                dirs_last=dirs_last,
                                                info_first=info_first)

            # If there are multiple labels in the group, make sure each label
            # is adjacent to any data files of the same name. This can comes up
            # with Juno JIRAM, at least.
            labels = [basename for basename in sorted
                      if self.parent_pdsf.basename_is_label(basename)]
            if len(labels) > 1:
              for label in labels:
                l = sorted.index(label)                     # index of label
                pattern = os.path.splitext(label)[0] + '.'
                tlist = [t for t in range(len(sorted))      # indices of targets
                         if sorted[t].startswith(pattern)]
                tlist.remove(l)

                # If the label is not adjacent, but could be...
                if tlist and (l+1) not in tlist and (l-1) not in tlist:
                    # Locate the nearest target with a matching basename
                    diffs = [(abs(t-l),t) for t in tlist]
                    tbest = min(diffs)[1]

                    # Relocate the label to an adjacent location
                    if l < tbest:
                        sorted.insert(tbest - 1, sorted.pop(l))
                    else:
                        sorted.insert(tbest + 1, sorted.pop(l))

        else:
            sorted = list(basename_dict.keys())     # for merged directories
            sorted.sort()

        self.rows = [basename_dict[key] for key in sorted]

    def sort(self, labels_after=None, dirs_first=None, dirs_last=None,
                   info_first=None):
        """Sort the rows of this group."""

        basename_dict = {pdsf.basename:pdsf for pdsf in self.rows}

        if self.parent_pdsf:
            sorted = self.parent_pdsf.sort_basenames(list(basename_dict.keys()),
                                                labels_after=labels_after,
                                                dirs_first=dirs_first,
                                                dirs_last=dirs_last,
                                                info_first=info_first)

            # If there are multiple labels in the group, make sure each label
            # is adjacent to any data files of the same name. This can comes up
            # with Juno JIRAM, at least.
            labels = [basename for basename in sorted
                      if self.parent_pdsf.basename_is_label(basename)]
            if len(labels) > 1:
              for label in labels:
                l = sorted.index(label)                     # index of label
                pattern = os.path.splitext(label)[0] + '.'
                tlist = [t for t in range(len(sorted))      # indices of targets
                         if sorted[t].startswith(pattern)]
                tlist.remove(l)

                # If the label is not adjacent, but could be...
                if tlist and (l+1) not in tlist and (l-1) not in tlist:

                    # Locate the nearest target with a matching basename
                    diffs = [(abs(t-l),t) for t in tlist]
                    tbest = min(diffs)[1]

                    # Relocate the label to an adjacent location
                    if l < tbest:
                        sorted.insert(tbest - 1, sorted.pop(l))
                    else:
                        sorted.insert(tbest + 1, sorted.pop(l))

        else:
            sorted = list(basename_dict.keys())     # for merged directories
            sorted.sort()

        self.rows = [basename_dict[key] for key in sorted]

    def append(self, pdsf, hidden=False):
        """Add the given PdsFile to this group."""

        # Initialize if necessary
        if self.parent_pdsf is False:
            self.parent_pdsf = pdsf.parent()
            self.rows = [pdsf]
            self.anchor = pdsf.anchor
            return

        if self.anchor is None:
            self.anchor = pdsf.anchor

        # Same parent required
        if pdsf.parent_logical_path != self.parent_logical_path:
            raise ValueError('PdsFile does not match parent of PdsGroup: ' +
                             pdsf.parent_logical_path + ', ' +
                             self.parent_logical_path)

        # Same anchor required
        if pdsf.anchor != self.anchor:
            raise ValueError('PdsFile does not match anchor of PdsGroup: ' +
                             pdsf.anchor + ', ' + self.anchor)

        # Ignore duplicates
        for row in self.rows:
            if pdsf.logical_path == row.logical_path:
                return

        self.rows.append(pdsf)
        if hidden:
            self.hidden |= {pdsf.logical_path}

        self._isdir_filled = None
        self._iconset_filled = None
        self._viewset_filled = None
        self._local_viewset_filled = None

    def remove(self, pdsf):
        """Remove the PdsFile from this PdsGroup. Return True if the PdsFile
        was removed, False if it is not a member.
        """

        for k in range(len(self.rows)):
            logical_path = self.rows[k].logical_path
            if logical_path == pdsf.logical_path:
                del self.rows[k]
                self.hidden -= {logical_path}
                return True

        return False

    def hide(self, pdsf):
        """Hide the PdsFile in this PdsGroup. Return True if the PdsFile was
        hidden, False if it is not a member.
        """

        for k in range(len(self.rows)):
            if self.rows[k].logical_path == pdsf.logical_path:
                if pdsf.logical_path not in self.hidden:
                    self.hidden |= {pdsf.logical_path}
                    return True

        return False

    def hide_all(self):
        """Hide all the PdsFiles in this PdsGroup."""

        paths = [f.logical_path for f in self.rows]
        self.hidden = set(paths)

    def unhide(self, pdsf):
        """Unhide the PdsFile in this PdsGroup. Return True if the PdsFile was
        un-hidden, False if it is not a member.
        """

        for k in range(len(self.rows)):
            if self.rows[k].logical_path == pdsf.logical_path:
                if pdsf.logical_path in self.hidden:
                    self.hidden -= {pdsf.logical_path}
                    return True

        return False

    def unhide_all(self):
        """Un-hide all the PdsFiles in this PdsGroup."""
        self.hidden = set()

    def iterator(self):
        """List of the rows of this PdsGroup, skipping hidden members."""
        return [r for r in self.rows if r.logical_path not in self.hidden]

    def iterator_for_all(self):
        """Iterator for the rows of this PdsGroup, hidden or not."""
        return [r for r in self.rows]

    def iterator_for_hidden(self):
        """List of the hidden rows of this PdsGroup."""
        return [r for r in self.rows if r.logical_path in self.hidden]

    ############################################################################
    # PdsFile grouping
    ############################################################################

    @staticmethod
    def group_children(pdsf, basenames=None):
        """Return children of this PdsFile as a list of PdsGroup objects."""

        if basenames is None:
            basenames = pdsf.childnames

        # Group basenames by anchor
        anchor_dict = {}
        for basename in basenames:
            anchor = pdsf.split_basename(basename)[0]
            if anchor not in anchor_dict:
                anchor_dict[anchor] = []

            anchor_dict[anchor].append(basename)

        # Sort basenames within each group; re-key by first basename
        basename_dict = {}
        for (anchor, basenames) in anchor_dict.items():
            sorted = pdsf.sort_basenames(basenames, labels_after=True)
            basename_dict[sorted[0]] = sorted

        # Sort keys
        keys = basename_dict.keys()
        keys = pdsf.sort_basenames(keys)

        # Return a list of lists of PdsGroup objects
        groups = []
        for key in keys:
            basenames = basename_dict[key]
            groups.append(PdsGroup(pdsf.pdsfiles_for_basenames(basenames)))

        return groups

################################################################################
