"""Table utilities for organizing PdsGroups in Viewmaster.

This module defines `PdsGroupTable`, an ordered collection of `PdsGroup`
objects that share a common parent directory. In Viewmaster, a
`PdsGroupTable` represents a single table section where groups are rendered
as rows. Individual groups within a table can be hidden from display while
remaining in the collection.
"""

import pdsfile
from . import pdsgroup

class PdsGroupTable(object):
    """An ordered collection of PdsGroups sharing a common parent.

    PdsGroupTable organizes groups of related PdsFiles into a single table
    section. All groups must share the same parent directory. Groups can be
    hidden, in which case the default iterator excludes them.

    Attributes:
        parent_pdsf: Parent `Pds3File` (False until initialized; None for
            merged directories).
        groups (list): Ordered list of `PdsGroup` objects.
        _levels_filled (list|None): Cached parent hierarchy levels.
    """

    def __init__(self, pdsgroups=None, parent=False):
        """Initialize a PdsGroupTable.

        Parameters:
            pdsgroups (list|None): Initial groups to add.
            parent (Pds3File|bool|None): Common parent; False to derive from
                the first inserted group; None indicates a merged directory.

        Returns:
            None
        """

        self.parent_pdsf = parent   # False for un-initialized; None for merged
        self.groups = []
        self._levels_filled = None

        for group in (pdsgroups or []):
            self.insert_group(group)

    def __repr__(self):
        """Debug representation of the table.

        Returns:
            str: Representation with first member path and total count.
        """

        first = None
        count = 0
        for group in self.groups:
            count += len(group.rows)
            if not first and group.rows:
                first = group.rows[0].logical_path

        if count > 1:
            return f'PdsGroupTable({first},...[{count}])'

        elif count == 1:
            return f'PdsGroupTable({first})'

        else:
            return f'PdsGroupTable()'

    def copy(self):
        """Create a shallow copy of the table.

        Returns:
            PdsGroupTable: A new table with copied groups and metadata.
        """

        this = PdsGroupTable()
        this.parent_pdsf = self.parent_pdsf
        this.groups = [g.copy() for g in self.groups]
        this._levels_filled = self._levels_filled

        return this

    @property
    def parent_logical_path(self):
        """Logical path of the parent directory.

        Returns:
            str: Parent logical path or empty string if unknown.
        """

        if self.parent_pdsf:
            return self.parent_pdsf.logical_path
        else:
            return ''

    @property
    def levels(self):
        """Hierarchy of parent directories from root to this table's parent.

        Returns:
            list: List of PdsFile objects representing the parent hierarchy.
        """

        if self._levels_filled is None:
            levels = []
            pdsf = self.parent_pdsf
            while pdsf:
                levels.append(pdsf)
                pdsf = pdsf.parent()

            self._levels_filled = levels

        return self._levels_filled

    @property
    def levels_plus_one(self):
        """Parent hierarchy plus the first member of the first group.

        Returns:
            list: First member of the first group followed by parent hierarchy levels.
        """

        return [self.groups[0].rows[0]] + self.levels

    def iterator(self):
        """Return visible groups only (those with at least one visible member).

        Returns:
            list: Groups with non-zero visible member count.
        """

        return [g for g in self.groups if len(g) > 0]

    def iterator_for_all(self):
        """Return all groups, including those with all members hidden.

        Returns:
            list: All groups in the table.
        """

        return [g for g in self.groups]

    def iterator_for_hidden(self):
        """Return groups where all members are hidden.

        Returns:
            list: Groups with zero visible members.
        """

        return [g for g in self.groups if len(g) == 0]

    def pdsfile_iterator(self):
        """Collect all visible PdsFiles from all groups.

        Returns:
            list: All visible PdsFiles across all groups.
        """

        pdsfiles = []
        for group in self.groups:
            pdsfiles += group.iterator()

        return pdsfiles

    def pdsfile_iterator_for_all(self):
        """Collect all PdsFiles from all groups, including hidden.

        Returns:
            list: All PdsFiles across all groups, visible and hidden.
        """

        pdsfiles = []
        for group in self.groups:
            pdsfiles += group.iterator_for_all()

        return pdsfiles

    def pdsfile_iterator_for_hidden(self):
        """Collect only hidden PdsFiles from all groups.

        Returns:
            list: All hidden PdsFiles across all groups.
        """

        pdsfiles = []
        for group in self.groups:
            pdsfiles += group.iterator_for_hidden()

        return pdsfiles

    def __len__(self):
        """Number of visible groups in the table.

        Returns:
            int: Count of groups with at least one visible member.
        """

        return len(self.iterator())

    def insert_group(self, group, merge=True):
        """Insert a group into the table, optionally merging with existing groups.

        Parameters:
            group (PdsGroup): Group to insert.
            merge (bool): If True and a group with the same anchor exists,
                merge members into it; otherwise append as a new group.

        Raises:
            ValueError: If the group's parent does not match the table's parent.

        Returns:
            None
        """

        if len(group.rows) == 0: return

        # Matching parent
        if self.parent_pdsf is False:
            self.parent_pdsf = group.parent_pdsf
        elif group.parent_logical_path != self.parent_logical_path:
            raise ValueError('PdsGroup parent does not match PdsGroupTable ' +
                             'parent')

        # Append to existing group if anchor matches
        if merge:
            for existing_group in self.groups:
                if existing_group.anchor == group.anchor:
                    for pdsf in group.rows:
                        hidden = (pdsf.logical_path in group.hidden)
                        existing_group.append(pdsf, hidden)

                    return

        # Otherwise, just append
        self.groups.append(group)

    def insert_file(self, pdsf, hidden=False):
        """Insert a PdsFile into the table, creating or merging into a group.

        Parameters:
            pdsf: PdsFile to insert.
            hidden (bool): If True, mark the file as hidden.

        Returns:
            None
        """

        parent_pdsf = pdsf.parent()
        if self.parent_pdsf is False:
            self.parent_pdsf = parent_pdsf

        # Append to existing group if anchor matches
        for existing_group in self.groups:
            if existing_group.anchor == pdsf.anchor:
                existing_group.append(pdsf, hidden)
                return

        # Otherwise, append a new group
        if hidden:
            self.insert_group(pdsgroup.PdsGroup([pdsf], parent=parent_pdsf,
                              hidden=[pdsf.logical_path]))
        else:
            self.insert_group(pdsgroup.PdsGroup([pdsf], parent=parent_pdsf))

    def insert(self, things):
        """Insert one or more items into the table.

        Accepts PdsFiles, PdsGroups, PdsGroupTables, or logical/absolute paths.
        Lists and tuples are processed recursively.

        Parameters:
            things: Item(s) to insert. Can be a PdsFile, PdsGroup,
                PdsGroupTable, logical path string, absolute path string, or
                list/tuple of any of these.

        Raises:
            TypeError: If the item type is not recognized.

        Returns:
            None
        """

        if type(things) in (list,tuple):
            for thing in things:
                self.insert(thing)

            return

        thing = things

        if isinstance(thing, str):
            for class_name in [pdsfile.Pds3File, pdsfile.Pds4File]:
                try:
                    pdsf = class_name.from_logical_path(thing)
                except ValueError:
                    try:
                        pdsf = class_name.from_abspath(thing)
                    except ValueError:
                        continue
                break

            self.insert_file(pdsf)

        elif isinstance(thing, PdsGroupTable):
            for group in thing.groups:
                self.insert_group(group)

        elif isinstance(thing, pdsgroup.PdsGroup):
            self.insert_group(thing)

        elif isinstance(thing, pdsfile.Pds3File) or isinstance(thing, pdsfile.Pds4File):
            self.insert_file(thing)

        else:
            raise TypeError('Unrecognized type for insert: ' +
                            type(thing).__name__)

    def sort_in_groups(self, labels_after=None, dirs_first=None, dirs_last=None,
                             info_first=None):
        """Sort members (PdsFiles) within each group (PdsGroup).

        Parameters:
            labels_after (bool|None): Place labels after their targets.
            dirs_first (bool|None): Sort directories before files.
            dirs_last (bool|None): Sort directories after files.
            info_first (bool|None): Prioritize info files.

        Returns:
            None
        """

        for group in self.groups:
            group.sort(labels_after=labels_after,
                       dirs_first=dirs_first,
                       dirs_last=dirs_last,
                       info_first=info_first)

    def sort_groups(self, labels_after=None, dirs_first=None, dirs_last=None,
                          info_first=None):
        """Sort the groups themselves by their first member's basename.

        Parameters:
            labels_after (bool|None): Place labels after their targets.
            dirs_first (bool|None): Sort directories before files.
            dirs_last (bool|None): Sort directories after files.
            info_first (bool|None): Prioritize info files.

        Returns:
            None
        """

        first_basenames = []
        group_dict = {}
        for group in self.groups:
            if group.rows:          # delete empty groups
                first_pdsf = group.rows[0]
                first_basename = first_pdsf.basename
                first_basenames.append(first_basename)
                group_dict[first_basename] = group

        if self.parent_pdsf:
            sorted_basenames = self.parent_pdsf.sort_basenames(first_basenames,
                                                      labels_after=labels_after,
                                                      dirs_first=dirs_first,
                                                      dirs_last=dirs_last,
                                                      info_first=info_first)
        else:
            sorted_basenames = list(first_basenames)
            sorted_basenames.sort()

        new_groups = [group_dict[k] for k in sorted_basenames]
        self.groups = new_groups

    def hide_pdsfile(self, pdsf):
        """Hide a PdsFile across all groups in the table.

        Parameters:
            pdsf: PdsFile to hide.

        Returns:
            bool: True if the file was found and hidden; False otherwise.
        """

        for group in self.groups:
            test = group.hide(pdsf)
            if test: return test

        return False

    def remove_pdsfile(self, pdsf):
        """Remove a PdsFile from all groups in the table.

        Parameters:
            pdsf: PdsFile to remove.

        Returns:
            bool: True if the file was found and removed; False otherwise.
        """

        for group in self.groups:
            test = group.remove(pdsf)
            if test: return test

        return False

    def filter(self, regex):
        """Hide files whose basenames do not match the regex pattern.

        Parameters:
            regex (re.Pattern): Compiled regex pattern to match against basenames.

        Returns:
            None
        """

        for pdsf in self.pdsfile_iterator():
            if not regex.match(pdsf.basename):
                self.hide_pdsfile(pdsf)

    @staticmethod
    def sort_tables(tables):
        """Sort tables by their parent logical paths.

        Parameters:
            tables (list): List of PdsGroupTable objects to sort.

        Returns:
            list: Tables sorted by parent logical path (empty string first).
        """

        sort_paths = []
        table_dict = {}
        for table in tables:
            if table.parent_pdsf is None:
                sort_path = ''
            else:
                sort_path = table.parent_logical_path

            sort_paths.append(sort_path)
            table_dict[sort_path] = table

        sort_paths.sort()
        return [table_dict[k] for k in sort_paths]

    @staticmethod
    def tables_from_pdsfiles(pdsfiles, exclusions=set(), hidden=set(),
                                       labels_after=None, dirs_first=None,
                                       dirs_last=None, info_first=None):
        """Create and organize PdsGroupTables from a list of PdsFiles.

        Groups files by parent directory, applies sorting rules, and excludes
        specified files. Returns a sorted list of tables.

        Parameters:
            pdsfiles (list): PdsFiles or logical path strings to organize.
            exclusions (set): Logical paths or abspaths to exclude.
            hidden (set): Logical paths to mark as hidden initially.
            labels_after (bool|None): Place labels after their targets.
            dirs_first (bool|None): Sort directories before files.
            dirs_last (bool|None): Sort directories after files.
            info_first (bool|None): Prioritize info files.

        Returns:
            list: Sorted list of PdsGroupTable objects.
        """

        # Exclusions list can be given as PdsFiles, logical paths, or abspaths
        new_exclusions = set()
        for item in exclusions:
            if isinstance(item, pdsfile.Pds3File) or isinstance(item, pdsfile.Pds4File):
                new_exclusions.add(item.logical_path)
            else:
                new_exclusions.add(item)
        exclusions = new_exclusions

        table_dict = {}
        for pdsf in pdsfiles:
            if isinstance(pdsf, str):
                for class_name in [pdsfile.Pds3File, pdsfile.Pds4File]:
                    try:
                        pdsf = class_name._from_absolute_or_logical_path(pdsf)
                    except ValueError:
                        continue
                    break

            if pdsf.logical_path in exclusions: continue
            if pdsf.abspath in exclusions: continue

            parent_pdsf = pdsf.parent()
            parent_path = parent_pdsf.logical_path if parent_pdsf else ''

            if parent_path not in table_dict:
                table_dict[parent_path] = PdsGroupTable(parent=parent_pdsf)

            table = table_dict[parent_path]
            is_hidden = (pdsf.logical_path in hidden)
            table.insert_file(pdsf, is_hidden)

        # If an excluded file happens to fall in the same parent directory as
        # one of these, include it after all.
#         for exclusion in exclusions:
#             parent_path = '/'.join(exclusion.split('/')[:-1])
#             if parent_path in table_dict and \
#                 not pdsfile.PdsFile.from_logical_path(exclusion).isdir:
#
#                 table_dict[parent_path].insert_file(
#                           pdsfile.PdsFile.from_logical_path(exclusion))

        for (key, table) in table_dict.items():
            if key.lower().endswith('.tab'): continue

            table.sort_in_groups(labels_after=labels_after,
                                 dirs_first=dirs_first,
                                 dirs_last=dirs_last,
                                 info_first=info_first)

            table.sort_groups(labels_after=labels_after,
                              dirs_first=dirs_first,
                              dirs_last=dirs_last,
                              info_first=info_first)

        tables = table_dict.values()
        tables = PdsGroupTable.sort_tables(tables)
        return tables

    def remove_hidden(self):
        """Create a copy of the table with all hidden members removed.

        Returns:
            PdsGroupTable: A new table containing only visible members.
        """

        new_table = self.copy()

        new_groups = []
        for group in self.groups:
            new_rows = list(group.iterator())
            if new_rows:
                new_group = group.copy()
                new_group.rows = new_rows
                new_group.hidden = set()
                new_groups.append(new_group)

        new_table.groups = new_groups
        return new_table

    @staticmethod
    def merge_index_row_tables(tables):
        """Merge index row tables by grandparent instead of parent.

        Reorganizes tables so that index rows sharing a grandparent are
        combined into a single table under that grandparent.

        Parameters:
            tables (list): Sorted list of PdsGroupTable objects, some of which
                may contain index rows.

        Returns:
            list: Modified list with index row tables merged by grandparent.
        """

        # Location for a table in the process of being merged
        merged_table_path = ''
        merged_table = None

        # Copy given tables into the new list...
        new_tables = []
        for table in tables:

            # Save this in the merged table if appropriate
            if (table.parent_pdsf.is_index and
                table.parent_pdsf.parent_logical_path == merged_table_path):
                    merged_table.groups += table.groups
                    continue

            # Otherwise, we're done with this merged table
            if merged_table:
                new_tables.append(merged_table)
                merged_table = None
                merged_table_path = ''

            # If this table does not contain an index row, we're done
            if not table.parent_pdsf.is_index:
                new_tables.append(table)
                continue

            # Start a new merged table
            merged_table_path = table.parent_pdsf.parent_logical_path
            merged_table = table
            merged_table.parent_pdsf = table.parent_pdsf.parent()
            merged_table_path = merged_table.parent_pdsf.logical_path
            merged_table._levels_filled = None

        # If we still have a merged table in reserve, append it to the list
        if merged_table:
            new_tables.append(merged_table)

        return new_tables

################################################################################
