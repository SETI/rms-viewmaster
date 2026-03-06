"""Iterator classes for navigating related PDS files and directories.

This module provides three iterator classes for traversing PdsFile structures:

    * `PdsDirIterator`: Iterates across related directories, jumping into adjacent
      directories and parallel volumes when required.
    * `PdsFileIterator`: Iterates through files within directories, with support
      for jumping to adjacent directories when needed.
    * `PdsRowIterator`: Simple iterator for files within a single directory
      (siblings only). It's used for index row navigation where each row is a sibling in
      the same table.

All iterators support both forward and backward iteration and can navigate
across directory boundaries when configured to do so.
"""

import os
import fnmatch
import pdsfile
import pdslogger

# Useful filters
def dirs_only(parent_pdsfile, basename):
    """Filter function that only returns directories.

    Parameters:
        parent_pdsfile: Parent PdsFile object, or None.
        basename (str): Basename of the child to check.

    Returns:
        bool: True if the child is a directory (or if parent is None);
            False otherwise.
    """

    if parent_pdsfile is None: return True

    child_pdsfile = parent_pdsfile.child(basename)
    return child_pdsfile.isdir


################################################################################
# Cache
################################################################################

DIRECTORY_CACHE = {}

################################################################################
# PdsDirIterator
################################################################################

class PdsDirIterator(object):
    """Iterator for navigating across related directories.

    Iterates across related directories, jumping into adjacent directories and
    parallel volumes when required. Uses a global directory cache to optimize
    performance. Supports both forward and backward iteration.

    Attributes:
        neighbors (list): List of logical paths for neighboring directories.
        neighbor_index (int): Current index in the neighbors list.
        current_logical_path (str): Logical path of the current directory.
        sign (int): Direction of iteration (+1 for forward, -1 for backward).
        logger: Optional logger instance for debugging.
    """

    def __init__(self, pdsf, sign=1, logger=None):
        """Initialize a PdsDirIterator.

        Parameters:
            pdsf: PdsFile representing the starting directory. If None, creates
                an empty iterator.
            sign (int): Direction of iteration (+1 for forward, -1 for backward).
            logger: Optional logger instance.

        Returns:
            None
        """

        global DIRECTORY_CACHE

        if pdsf is None:
            self.neighbors = []
            self.neighbor_index = 0
            self.current_logical_path = None
            self.sign = 1

        if isinstance(pdsf, pdsfile.Pds3File):
            pdsf_cls = pdsfile.Pds3File
        elif isinstance(pdsf, pdsfile.Pds4File):
            pdsf_cls = pdsfile.Pds4File

        fnmatch_patterns = pdsf.NEIGHBORS.first(pdsf.logical_path)
        if isinstance(fnmatch_patterns, str):
            fnmatch_patterns = (fnmatch_patterns,)

        if fnmatch_patterns:
            if fnmatch_patterns in DIRECTORY_CACHE:
                logical_paths = DIRECTORY_CACHE[fnmatch_patterns]
            else:
                paths = []
                for fnmatch_pattern in fnmatch_patterns:
                    abspaths = pdsf_cls.glob_glob(pdsf.root_ +
                                                         fnmatch_pattern)
                    abspaths = [pdsfile.pdsfile.repair_case(p, pdsf_cls)
                                for p in abspaths]
                    abspaths = [a for a in abspaths if os.path.isdir(a)]
                    paths += pdsf_cls.logicals_for_abspaths(abspaths)

                # Remove duplicates
                paths = list(set(paths))

                # Remove blanks (although they shouldn't be there)
                if '' in paths:
                    paths.remove('')

                # Sort based on the rules
                logical_paths = pdsf_cls.sort_logical_paths(paths)
                DIRECTORY_CACHE[fnmatch_patterns] = logical_paths

        else:
            logical_paths = [pdsf.logical_path]

        # Case insensitive search
        logical_paths_lc = [p.lower() for p in logical_paths]
        this_path_lc = pdsf.logical_path.lower()
        try:
            self.neighbor_index = logical_paths_lc.index(this_path_lc)
        except ValueError:
            logical_paths.append(pdsf.logical_path)
            logical_paths = pdsf_cls.sort_logical_paths(logical_paths)
            self.neighbor_index = logical_paths.index(pdsf.logical_path)

        self.sign = -1 if sign < 0 else +1

        self.neighbors = logical_paths
        self.neighbors_lc = [p.lower() for p in logical_paths]
        self.current_logical_path = pdsf.logical_path
        self.logger = logger

    def copy(self, sign=None):
        """Create a clone of this iterator, optionally with reversed direction.

        Parameters:
            sign (int|None): New direction (+1 forward, -1 backward). If None,
                preserves the current direction.

        Returns:
            PdsDirIterator: A new iterator starting from the same position.
        """

        if sign is None:
            sign1 = self.sign
        else:
            sign1 = -1 if sign < 0 else +1

        for class_name in [pdsfile.Pds3File, pdsfile.Pds4File]:
            try:
                pdsf = class_name.from_logical_path(self.current_logical_path)
            except ValueError:
                continue
            break
        this = PdsDirIterator(pdsf, sign=sign1, logger=self.logger)

        return this

    ############################################################################
    # Iterator
    ############################################################################

    def __iter__(self):
        """Return the iterator object itself.

        Returns:
            PdsDirIterator: The iterator instance.
        """

        return self

    def next(self):
        """Python 2 compatibility wrapper for __next__.

        Returns:
            tuple: (logical_path, display_path, level)

        Raises:
            StopIteration: When iteration is complete.
        """

        return self.__next__()

    def __next__(self):
        """Return the next neighbor directory in the iteration.

        Returns:
            tuple: A tuple (logical_path, display_path, level) where:
                - logical_path (str): Full logical path of the neighbor.
                - display_path (str): The string starting where 'prev' and 'this' differ
                - level (int): 0 if same directory level, 1 if different level.

        Raises:
            StopIteration: When no more neighbors are available.
        """

        prev_logical_path = self.current_logical_path

        # Try to return the next neighbor
        self.neighbor_index += self.sign
        if (self.neighbor_index < 0 or
            self.neighbor_index >= len(self.neighbors)):
                raise StopIteration

        # If we get this far, figure out what to return

        # Find the common parts of the previous logical path and this one
        neighbor = self.neighbors[self.neighbor_index]
        prev_parts = prev_logical_path.split('/')
        new_parts = neighbor.split('/')

        for k in range(len(prev_parts)):
            if prev_parts[k] != new_parts[k]:
                break

        # The display path is the string starting where prev and this differ
        new_parts = new_parts[k:]
        display_path = '/'.join(new_parts)

        # Level is 0 if prev and this are the same up to the basename; otherwise
        # level is 1.
        if len(new_parts) == 1:
            level = 0
        else:
            level = 1

        return (neighbor, display_path, level)

################################################################################
# PdsFileIterator
################################################################################

class PdsFileIterator(object):
    """Iterator for navigating through files within and across directories.

    Iterates through files within directories, with support for jumping to
    adjacent directories (cousins) when needed. Supports pattern matching,
    exclusion patterns, and custom filter functions.

    Attributes:
        parent: Parent PdsFile of the starting file.
        dir_iterator: PdsDirIterator for navigating parent directories.
        pattern (str|None): Optional fnmatch pattern for file names.
        exclude (str|None): Optional fnmatch exclusion pattern.
        filter (callable|None): Optional custom filter function.
        sign (int): Direction of iteration (+1 for forward, -1 for backward).
        current_logical_path (str): Logical path of the current file.
        sibnames (list): List of logical paths for sibling files.
        sibnames_lc (list): Lowercase version of sibnames for case-insensitive
            matching.
        sibling_index (int): Current index in the sibling list.
        logger: Optional logger instance.
    """

    def __init__(self, pdsf, sign=1, pattern=None, exclude=None, filter=None,
                       logger=None):
        """Initialize a PdsFileIterator.

        Parameters:
            pdsf: PdsFile representing the starting file.
            sign (int): Direction of iteration (+1 for forward, -1 for backward).
            pattern (str|None): Optional fnmatch pattern to match file names.
            exclude (str|None): Optional fnmatch pattern to exclude file names.
            filter (callable|None): Optional filter function taking
                (parent_pdsfile, basename) and returning bool.
            logger: Optional logger instance.

        Returns:
            None
        """

        self.parent = pdsf.parent()
        self.dir_iterator = PdsDirIterator(self.parent, sign, logger=logger)

        self.pattern = pattern
        self.exclude = exclude
        self.filter = filter
        self.sign = self.dir_iterator.sign
        self.current_logical_path = pdsf.logical_path

        # the pattern applies to the basenam
        basenames = self.parent.sort_basenames(self.parent.childnames)
        basenames = self._filter_names(basenames)
        basenames_lc = [n.lower() for n in basenames]

        # If this object is missing, insert it into the list of siblings
        if pdsf.basename.lower() not in basenames_lc:
            basenames.append(pdsf.basename)
            basenames = self.parent.sort_basenames(basenames)

        self.sibnames = self.parent.logicals_for_basenames(basenames)
        self.sibnames_lc = [n.lower() for n in self.sibnames]
        self.logger = logger

        # Case-insensitive search
        logical_path_lc = pdsf.logical_path.lower()
        self.sibling_index = self.sibnames_lc.index(logical_path_lc)

    def copy(self, sign=None):
        """Return a clone of this iterator."""

        if sign is None:
            sign1 = self.sign
        else:
            sign1 = -1 if sign < 0 else +1

        for class_name in [pdsfile.Pds3File, pdsfile.Pds4File]:
            try:
                pdsf = class_name.from_logical_path(self.current_logical_path)
            except ValueError:
                continue
            break
        this = PdsFileIterator(pdsf, sign=sign1,
                               pattern=self.pattern, exclude=self.exclude,
                               filter=self.filter, logger=self.logger)

        return this

    def _filter_names(self, basenames):
        """Apply pattern matching, exclusion, and custom filters to basenames.

        Parameters:
            basenames (list): List of basenames to filter.

        Returns:
            list: Filtered list of basenames.
        """

        if self.pattern:
            basenames = [s for s in basenames
                         if fnmatch.fnmatch(s, self.pattern)]
        if self.exclude:
            basenames = [s for s in basenames
                         if not fnmatch.fnmatch(s, self.exclude)]
        if self.filter:
            basenames = [s for s in basenames if self.filter(self.parent, s)]

        return basenames

    ############################################################################
    # Iterator
    ############################################################################

    def __iter__(self):
        """Return the iterator object itself.

        Returns:
            PdsFileIterator: The iterator instance.
        """

        return self

    def next(self):
        """Python 2 compatibility wrapper for __next__.

        Returns:
            tuple: (logical_path, display_path, level)

        Raises:
            StopIteration: When iteration is complete.
        """

        return self.__next__()

    def __next__(self):
        """Return the next file in the iteration, jumping to adjacent directories if needed.

        Returns:
            tuple: A tuple (logical_path, display_path, level) where:
                - logical_path (str): Full logical path of the file.
                - display_path (str): The part of the path that has changed.
                    At level 0, it is basename;
                    At level 1, it is parent directory/basename;
                - level (int): 0 for a sibling (same directory), 1 for a cousin
                    (different directory).

        Raises:
            StopIteration: When no more files are available.
        """

        # Try to return the next sibling
        try:
            self.sibling_index += self.sign
            if self.sibling_index < 0:
                raise IndexError()

            sibname = self.sibnames[self.sibling_index]

        # Jump to adjacent directory if necessary
        except IndexError:
            return self.next_cousin()

        # Otherwise return the next sibling
        else:
            self.current_logical_path = sibname
            return (sibname, os.path.basename(sibname), 0)

    def next_cousin(self):
        """Move iteration to an adjacent parent directory and return the first file.

        This method is called when the current directory's files are exhausted.
        It navigates to the next/previous parent directory and loads its files.

        Returns:
            tuple: A tuple (logical_path, display_path, level=1) where:
                - logical_path (str): Full logical path of the file.
                - display_path (str): Parent directory path plus basename.
                - level (int): Always 1 (cousin level).

        Raises:
            StopIteration: If no adjacent parent directory is available.
        """

        # Go to the next parent
        (parent_logical_path, parent_display_path, _) = self.dir_iterator.next()

        for class_name in [pdsfile.Pds3File, pdsfile.Pds4File]:
            try:
                self.parent = class_name.from_logical_path(parent_logical_path)
            except ValueError:
                continue
            break
        else:
            # Neither Pds3File nor Pds4File could create the parent
            raise ValueError(
                f"Could not create parent PdsFile from logical path "
                f"'{parent_logical_path}'. Neither pdsfile.Pds3File nor "
                f"pdsfile.Pds4File.from_logical_path() succeeded."
            )

        # Load the next set of siblings
        basenames = self.parent.sort_basenames(self.parent.childnames)
        basenames = self._filter_names(basenames)
        self.sibnames = self.parent.logicals_for_basenames(basenames)

        # Return the first new sibling
        if self.sign > 0:
            self.sibling_index = -1
        else:
            self.sibling_index = len(self.sibnames)

        (logical_path, basename, _) = self.next()
        return (logical_path, parent_display_path + '/' + basename, 1)

################################################################################
# PdsRowIterator
################################################################################

class PdsRowIterator(object):
    """Simple iterator for files within a single directory (siblings only).

    This iterator only navigates within the same parent directory and does not
    cross directory boundaries. It's used for index row navigation where each
    row is a sibling in the same table.

    Attributes:
        parent_pdsf: Parent PdsFile of the starting file.
        parent_logical_path_ (str): Logical path of the parent with trailing '/'.
        sign (int): Direction of iteration (+1 for forward, -1 for backward).
        sibnames (list): List of basenames for sibling files.
        sibnames_lc (list): Lowercase version of sibnames for case-insensitive
            matching.
        sibling_index (int): Current index in the sibling list.
        logger: Optional logger instance.
    """

    def __init__(self, pdsf, sign=1, logger=None):
        """Initialize a PdsRowIterator.

        Parameters:
            pdsf: PdsFile representing the starting file (typically an index row).
            sign (int): Direction of iteration (+1 for forward, -1 for backward).
            logger: Optional logger instance.

        Returns:
            None
        """

        self.parent_pdsf = pdsf.parent()
        self.parent_logical_path_ = self.parent_pdsf.logical_path + '/'

        self.sign = sign

        basenames = self.parent_pdsf.childnames
        basenames_lc = self.parent_pdsf.childnames_lc

        # If this object is missing, insert it into the list of siblings
        this_basename_lc = pdsf.basename.lower()
        if this_basename_lc not in basenames_lc:
            basenames.append(pdsf.basename)
            basenames = self.parent_pdsf.sort_basenames(basenames)
            basenames_lc = [n.lower() for n in basenames]

        self.sibnames = basenames
        self.sibnames_lc = basenames_lc
        self.sibling_index = basenames_lc.index(this_basename_lc)
        self.logger = logger

    def copy(self, sign=None):
        """Return a clone of this iterator."""

        if sign is None:
            sign1 = self.sign
        else:
            sign1 = -1 if sign < 0 else +1

        childname = self.sibnames[self.sibling_index]
        return PdsRowIterator(self.parent_pdsf.child(childname), sign=sign1,
                              logger=self.logger)

    ############################################################################
    # Iterator
    ############################################################################

    def __iter__(self):
        """Return the iterator object itself.

        Returns:
            PdsRowIterator: The iterator instance.
        """

        return self

    def next(self):
        """Python 2 compatibility wrapper for __next__.

        Returns:
            tuple: (logical_path, display_path, level)

        Raises:
            StopIteration: When iteration is complete.
        """

        return self.__next__()

    def __next__(self):
        """Return the next sibling file in the iteration.

        This iterator only returns siblings (level 0) and does not cross
        directory boundaries.

        Returns:
            tuple: A tuple (logical_path, display_path, level) where:
                - logical_path (str): Full logical path of the sibling file.
                - display_path (str): The part of the path that has changed.
                    At level 0, it is basename;
                    At level 1, it is parent directory/basename;
                - level (int): Always 0 (sibling level).

        Raises:
            StopIteration: When no more siblings are available.
        """

        self.sibling_index += self.sign
        if self.sibling_index < 0 or self.sibling_index >= len(self.sibnames):
            raise StopIteration

        sibname = self.sibnames[self.sibling_index]
        return (self.parent_logical_path_ + sibname, sibname, 0)

################################################################################
