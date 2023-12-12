################################################################################
# PdsGroupTable class. An ordered set of PdsGroups sharing a common parent.
# Some may be hidden. These are grouped together within a single table in
# Viewmaster.
################################################################################

import pdsfile
import pdsgroup

class PdsGroupTable(object):

    def __init__(self, pdsgroups=[], parent=False):

        self.parent_pdsf = parent   # False for un-initialized; None for merged
        self.groups = []
        self._levels_filled = None

        for group in pdsgroups:
            self.insert_group(group)

    def __repr__(self):
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
        this = PdsGroupTable()
        this.parent_pdsf = self.parent_pdsf
        this.groups = [g.copy() for g in self.groups]
        this._levels_filled = self._levels_filled

        return this

    @property
    def parent_logical_path(self):
        if self.parent_pdsf:
            return self.parent_pdsf.logical_path
        else:
            return ''

    @property
    def levels(self):
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
        return [self.groups[0].rows[0]] + self.levels

    def iterator(self):
        return [g for g in self.groups if len(g) > 0]

    def iterator_for_all(self):
        return [g for g in self.groups]

    def iterator_for_hidden(self):
        return [g for g in self.groups if len(g) == 0]

    def pdsfile_iterator(self):
        pdsfiles = []
        for group in self.groups:
            pdsfiles += group.iterator()

        return pdsfiles

    def pdsfile_iterator_for_all(self):
        pdsfiles = []
        for group in self.groups:
            pdsfiles += group.iterator_for_all()

        return pdsfiles

    def pdsfile_iterator_for_hidden(self):
        pdsfiles = []
        for group in self.groups:
            pdsfiles += group.iterator_for_hidden()

        return pdsfiles

    def __len__(self):
        return len(self.iterator())

    def insert_group(self, group, merge=True):

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

        if type(things) in (list,tuple):
            for thing in things:
                self.insert(thing)

            return

        thing = things

        if isinstance(thing, str):
            try:
                pdsf = pdsfile.PdsFile.from_logical_path(thing)
            except ValueError:
                pdsf = pdsfile.PdsFile.from_abspath(thing)

            self.insert_file(pdsf)

        elif isinstance(thing, PdsGroupTable):
            for group in thing.groups:
                self.insert_group(group)

        elif isinstance(thing, pdsgroup.PdsGroup):
            self.insert_group(thing)

        elif isinstance(thing, pdsfile.PdsFile):
            self.insert_file(thing)

        else:
            raise TypeError('Unrecognized type for insert: ' +
                            type(thing).__name__)

    def sort_in_groups(self, labels_after=None, dirs_first=None, dirs_last=None,
                             info_first=None):
        """Within each row of the table, sort the PdsFiles in the PdsGroup."""

        for group in self.groups:
            group.sort(labels_after=labels_after,
                       dirs_first=dirs_first,
                       dirs_last=dirs_last,
                       info_first=info_first)

    def sort_groups(self, labels_after=None, dirs_first=None, dirs_last=None,
                          info_first=None):
        """Within each row of the table, sort the PdsFiles in the PdsGroup."""

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
        for group in self.groups:
            test = group.hide(pdsf)
            if test: return test

        return False

    def remove_pdsfile(self, pdsf):
        for group in self.groups:
            test = group.remove(pdsf)
            if test: return test

        return False

    def filter(self, regex):
        for pdsf in self.pdsfile_iterator():
            if not regex.match(pdsf.basename):
                self.hide_pdsfile(pdsf)

    @staticmethod
    def sort_tables(tables):
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
        """Return a sorted list of PdsGroupTables accommodating the given list
        of PdsFiles."""

        # Exclusions list can be given as PdsFiles, logical paths, or abspaths
        new_exclusions = set()
        for item in exclusions:
            if isinstance(item, pdsfile.PdsFile):
                new_exclusions.add(item.logical_path)
            else:
                new_exclusions.add(item)
        exclusions = new_exclusions

        table_dict = {}
        for pdsf in pdsfiles:
            if isinstance(pdsf, str):
                pdsf = pdsfile.PdsFile._from_absolute_or_logical_path(pdsf)

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
        """Returns a modified list of tables in which index rows are organized
        by grandparent rather than by parent. The given list of tables must
        already by sorted.
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
