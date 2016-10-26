import numpy as np
import numbers
from lazy import lazy
from lazy import LazyOperation

class TimeSeries:
    """
    A class that stores a single, ordered set of numerical data.

    Parameters
    ----------
    values : list
        This can be any object that can be treated like a sequence. Mandatory.
    times : list
        This can be any object that can be treated like a sequence. Optional.
        If it is not supplied, equally spaced integers are used instead.
    position: int
        The index position at which the requested item should be inserted

    Notes
    -----
    PRE: `values` is sorted in non-decreasing order
    POST:

    INVARIANTS:

    WARNINGS:
    - Does not maintain an accurate time series if `input_data` is unsorted.
    """

    # J: maximum length of `values` after which
    # abbreviation will occur in __str__() and __repr__()
    MAX_LENGTH = 10

    def __init__(self, values, times=None):
        """
        The TimeSeries class constructor. It must be provided the initial data
        to fill the time series instance with.

        Parameters
        ----------
        values : sequence-like
            Actual data points for TimeSeries.
            Any user-provided sequence-like object. Mandatory.
        times : sequence-like
            Time values for TimeSeries. Optional.
            If None, equally spaced integers are used instead.

        Notes
        -----
        PRE: If times is not provided, `values` must be sorted
        POST:

        INVARIANTS:
        inital_data and times (if provided) must be sequences.

        WARNINGS:

        """

        # First confirm `inital_data` is a sequence.

        # J: unit test this
        # N: done
        # J: all Python sequences implement __iter__(), which we can use here.

        self.is_sequence(values)
        self._values = list(values)

        if times:
            self.is_sequence(times)
            self._times = list(times)

        else:
            self._times = list(range(len(self._values)))

        if len(self._times) != len(self._values):
            raise ValueError("Time and input data of incompatible dimensions")

        if len(self._times) != len(set(self._times)):
            raise ValueError("Time data should contain no repeats")

    def __len__(self):
        return len(self._values)

    def __getitem__(self, index):
        try:
            return self._values[index]
        except IndexError:
            raise IndexError("Index out of bounds!")

    def __setitem__(self, index, value):
        try:
            self._values[index] = value
        except IndexError:
            raise IndexError("Index out of bounds!")

    def __iter__(self):
        for val in self._values:
            yield val

    def itertimes(self):
        for tim in self._times:
            yield tim

    def itervalues(self):
        # R: Identical to __iter__
        for val in self._values:
            yield val

    def iteritems(self):
        for i in range(len(self._values)):
            yield self._times[i], self._values[i]

    def __contains__(self, needle):
        # R: leverages self._values is a list. Will have to change when we relax this.
        return needle in self._values

    def values(self):
        return np.array(self._values)

    def times(self):
        return np.array(self._times)

    def items(self):
        return list(zip(self._times, self._values))

    def __repr__(self):
        class_name = type(self).__name__
        return '{}(Length: {}, {})'.format(class_name,
                                           len(self._values),
                                           str(self))

    def __str__(self):
        """
        Description
        -----------
        Instance method for pretty-printing the TimeSeries contents.

        Parameters
        ----------
        self: TimeSeries instance

        Returns
        -------
        pretty_printed: string
            an end-user-friendly printout of the time series.
            If `len(self._values) > MAX_LENGTH`, printout abbreviated
            using an ellipsis: `['a','b','c', ..., 'x','y','z']`.

        Notes
        -----
        PRE:
        POST:

        INVARIANTS:

        WARNINGS:

        """
        if len(self._values) > self.MAX_LENGTH:
            needed = self._values[:3]+self._values[-3:]
            pretty_printed = "[{} {} {}, ..., {} {} {}]".format(*needed)

        else:
            pretty_printed = "{} {}".format(list(self._values), list(self._times))

        return pretty_printed

    @staticmethod
    def _check_length_helper(lhs , rhs):
        if not len(lhs)==len(rhs):
            raise ValueError(str(lhs)+' and '+str(rhs)+' must have the same length')

    @staticmethod
    # makes check lengths redundant. However I keep them separate in case we want to add functionality to add objects without a defined time dimension later.
    def _check_time_domains_helper(lhs , rhs):
        if not lhs._times==rhs._times:
            raise ValueError(str(lhs)+' and '+str(rhs)+' must have identical time domains')

    def __abs__(self):
        return math.sqrt(sum(x * x for x in self._values))

    def __bool__(self):
        return bool(abs(self._values))

    def __neg__(self):
        return TimeSeries((-x for x in self._values), self._times)

    def __pos__(self):
        return TimeSeries((x for x in self._values), self._times)

    def __add__(self, rhs):
        try:
            if isinstance(rhs, numbers.Real):
                return TimeSeries((a + rhs for a in self), self._times) # R: may be worth testing time domains are preserved correctly
            else:
                TimeSeries._check_length_helper(self, rhs)
                TimeSeries._check_time_domains_helper(self, rhs) # R: test me. should fail when the time domains are non congruent
                pairs = zip(self._values, rhs)
                return TimeSeries((a + b for a, b in pairs), self._times)
        except TypeError:
            raise NotImplemented # R: test me. should fail when we try to add a numpy array or list

    def __radd__(self, other): # other + self delegates to self.__add__
        return self + other

    def __sub__(self, rhs):
        try:
            if isinstance(rhs, numbers.Real):
                return TimeSeries((a - rhs for a in self), self._times)
            else:
                TimeSeries._check_length_helper(self, rhs)
                TimeSeries._check_time_domains_helper(self, rhs)
                pairs = zip(self._values, rhs)
                return TimeSeries((a - b for a, b in pairs), self._times)
        except TypeError:
            raise NotImplemented

    def __rsub__(self, other):
        return -(self - other)

    def __mul__(self, rhs):
        try:
            if isinstance(rhs, numbers.Real):
                return TimeSeries((a * rhs for a in self), self._times)
            else:
                TimeSeries._check_length_helper(self, rhs)
                TimeSeries._check_time_domains_helper(self, rhs)
                pairs = zip(self._values, rhs)
                return TimeSeries((a * b for a, b in pairs), self._times)
        except TypeError:
            raise NotImplemented

    def __rmul__(self, other):
        return self * other

    def __eq__(self, rhs):
        self.__class__._check_length_helper(self, rhs)
        self.__class__._check_time_domains_helper(self, rhs)
        # R: leverages self._values is a list. Will have to change when we relax this.
        try:
            return self._values==rhs._values
        except TypeError:
            raise NotImplemented

    def __ne__(self, other):
        return not self.__eq__(other)

    def is_sequence(self, seq):
        """
        Description
        -----------
        Checks if `seq` is a sequence by verifying if it implements __iter__.

        Parameters
        ----------
        self: TimeSeries instance
        seq: sequence

        Notes
        -----
        A better implementation might be to use
        and isinstance(seq, collections.Sequence)
        """
        try:
            _ = iter(seq)
        except TypeError as te:
            # J: unified string formatting with .format()
            raise TypeError("{} is not a valid sequence".format(seq))


    def interpolate(self,ts_to_interpolate):
        """
        Returns new TimeSeries instance with piecewise-linear-interpolated values
        for submitted time-times.If called times are outside of the domain of the existing
        Time Series, the minimum or maximum values are returned.

        Parameters
        ----------
        self: TimeSeries instance
        ts_to_interpolate: list or other sequence of times to be interpolated

        """
        def binary_search(times, t):
            """ Returns surrounding time indexes for value that is to be interpolated"""
            min = 0
            max = len(times) - 1
            while True:
                if max < min:
                    return (max,min)
                m = (min + max) // 2
                if times[m] < t:
                    min = m + 1
                elif times[m] > t:
                    max = m - 1
                else: #Should never hit this case in current implementation
                    return (min,max)

        def interpolate_val(times,values,t):
            """Returns interpolated value for given time"""

            if t in times:          #time already exits in ts -- return it
                return values[times.index(t)]

            elif t >= times[-1]:    #time is above the domain of the existing values -- return max time value
                return values[-1]

            elif t <= times[0]:     #time is below the domain of the existing values -- return min time value
                return values[0]

            else:                   #time is between two existing points -- interpolate it
                low,high = binary_search(times, t)
                slope = (float(values[high]) - values[low])/(times[high] - times[low])
                c = values[low]
                interpolated_val = (t-times[low])*slope + c
                return interpolated_val

        interpolated_ts = [interpolate_val(self._times,self._values,t) for t in ts_to_interpolate]
        return self.__class__(values=interpolated_ts,times=ts_to_interpolate)

    @lazy
    def identity(self):
        """
            An identity function with one argument that just returns the argument - self is the only argument

            Returns
            -------
            self : the instance to identify
        """
        return self

    @property
    def lazy(self):
        """
            A lazy property method that returns a new LazyOperation instance using the TimeSeries.identity() method

            Returns
            -------
            self.identity() : an instance of LazyOperation
        """
        return self.identity()