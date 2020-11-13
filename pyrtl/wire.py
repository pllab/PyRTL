"""
wire has the basic extended types useful for creating logic.

Types defined in this file include:

* `WireVector` -- the base class for ordered collections of wires
* `Input` -- a wire vector that receives an input for a block
* `Output` -- a wire vector that defines an output for a block
* `Const` -- a wire vector fed by a constant
* `Register` -- a wire vector that is latched each cycle
* `Bundle` -- a wire vector that has named fields for easy access
"""

from __future__ import print_function, unicode_literals

import numbers
import six
import re
import sys
from functools import reduce

from . import core  # needed for _setting_keep_wirevector_call_stack

from .pyrtlexceptions import PyrtlError, PyrtlInternalError
from .core import working_block, LogicNet, _NameIndexer

# ----------------------------------------------------------------
#        ___  __  ___  __   __
#  \  / |__  /  `  |  /  \ |__)
#   \/  |___ \__,  |  \__/ |  \
#


_wvIndexer = _NameIndexer("tmp")
_constIndexer = _NameIndexer("const_")


def _reset_wire_indexers():
    global _wvIndexer, _constIndexer
    _wvIndexer = _NameIndexer("tmp")
    _constIndexer = _NameIndexer("const_")


def next_tempvar_name(name=""):
    if name == '':  # sadly regex checks are sometimes too slow
        wire_name = _wvIndexer.make_valid_string()
        callpoint = core._get_useful_callpoint_name()
        if callpoint:  # returns none if debug mode is false
            filename, lineno = callpoint
            safename = re.sub(r'[\W]+', '', filename)  # strip out non alphanumeric characters
            wire_name += '_%s_line%d' % (safename, lineno)
        return wire_name
    else:
        if name.lower() in ['clk', 'clock']:
            raise PyrtlError('Clock signals should never be explicit')
        return name


class WireVector(object):
    """ The main class for describing the connections between operators.

    WireVectors act much like a list of wires, except that there is no
    "contained" type, each slice of a wirevector is itself a wirevector
    (even if it just contains a single "bit" of information).  The least
    significant bit of the wire is at index 0 and normal list slicing
    syntax applies (i.e. myvector[0:5] makes a new vector from the bottom
    5 bits of myvector, myvector[-1] takes the most significant bit, and
    myvector[-4:] takes the 4 most significant bits).

    ===============  ================  =======================================================
    Operation        Syntax            Function
    ===============  ================  =======================================================
    Addition         a + b             Creates an adder, returns WireVector
    Subtraction      a - b             Subtraction (twos complement)
    Multiplication   a * b             Creates an multiplier, returns WireVector
    Xor              a ^ b             Bitwise XOR, returns WireVector
    Or               a | b             Bitwise OR, returns WireVector
    And              a & b             Bitwise AND, returns WireVector
    Invert           ~a                Bitwise invert, returns WireVector
    Less Than        a < b             Less than, return 1-bit WireVector
    Less or Eq.      a <= b            Less than or Equal to, return 1-bit WireVector
    Greater Than     a > b             Greater than, return 1-bit WireVector
    Greater or Eq.   a >= b            Greater or Equal to, return 1-bit WireVector
    Equality         a == b            Hardware to check equality, return 1-bit WireVector
    Not Equal        a != b            Inverted equality check, return 1-bit WireVector
    Bitwidth         len(a)            Return bitwidth of the wirevector
    Assignment       a <<= b           Connect from b to a (see note below)
    Bit Slice        a[3:6]            Selects bits from wirevector, in this case bits 3,4,5
    ===============  ================  =======================================================

    A note on <<= asssignment: This operator is how you "drive" an already
    created wire with an existing wire.  If you were to do `a = b` it would lose the
    old value of `a` and simply overwrite it with a new value, in this case with a
    reference to wirevector `b`.  In contrast `a <<= b` does not overwrite `a`, but
    simply wires the two together.
    """

    # "code" is a static variable used when output as string.
    # Each class inheriting from WireVector should overload accordingly
    _code = 'W'

    def __init__(self, bitwidth=None, name='', block=None):
        """ Construct a generic WireVector

        :param int bitwidth: If no bitwidth is provided, it will be set to the
         minimum number of bits to represent this wire
        :param Block block: The block under which the wire should be placed.
         Defaults to the working block
        :param String name: The name of the wire referred to in some places.
         Must be unique. If none is provided, one will be autogenerated
        :return: a wirevector object representing a const wire
        """
        self._name = None

        # used only to verify the one to one relationship of wires and blocks
        self._block = working_block(block)
        self.name = next_tempvar_name(name)
        self._validate_bitwidth(bitwidth)

        # Each module tracks which wires belong to it
        if self._block.current_module:
            self._block.current_module[-1].add_wire(self)
            self.module = self._block.current_module[-1]

        if core._setting_keep_wirevector_call_stack:
            import traceback
            self.init_call_stack = traceback.format_stack()

    @property
    def name(self):
        """ A property holding the name (a string) of the WireVector, can be read or written.
            For example: `print(a.name)` or `a.name = 'mywire'`."""
        return self._name

    @name.setter
    def name(self, value):
        if not isinstance(value, six.string_types):
            raise PyrtlError('WireVector names must be strings')
        self._block.wirevector_by_name.pop(self._name, None)
        self._name = value
        self._block.add_wirevector(self)

    def __hash__(self):
        return id(self)

    def __str__(self):
        """ A string representation of the wire in 'name/bitwidth code' form. """
        return ''.join([self.name, '/', str(self.bitwidth), self._code])

    def _validate_bitwidth(self, bitwidth):
        if bitwidth is not None:
            if not isinstance(bitwidth, numbers.Integral):
                raise PyrtlError('bitwidth must be from type int or unspecified, instead "%s"'
                                 ' was passed of type %s' % (str(bitwidth), type(bitwidth)))
            elif bitwidth == 0:
                raise PyrtlError('bitwidth must be greater than or equal to 1')
            elif bitwidth < 0:
                raise PyrtlError('you are trying a negative bitwidth? awesome but wrong')
        self.bitwidth = bitwidth

    def _build(self, other):
        # Actually create and add wirevector to logic block
        # This might be called immediately from ilshift, or delayed from conditional assignment
        net = LogicNet(
            op='w',
            op_param=None,
            args=(other,),
            dests=(self,))
        working_block().add_net(net)

    def _prepare_for_assignment(self, rhs):
        # Convert right-hand-side to wires and propagate bitwidth if necessary
        from .corecircuits import as_wires
        rhs = as_wires(rhs, bitwidth=self.bitwidth)
        if self.bitwidth is None:
            self.bitwidth = rhs.bitwidth
        return rhs

    def __ilshift__(self, other):
        """ Wire assignment operator (assign other to self). """
        other = self._prepare_for_assignment(other)
        self._build(other)
        return self

    def __ior__(self, other):
        """ Conditional assignment operator (only valid under Conditional Update). """
        from .conditional import _build, currently_under_condition
        if not self.bitwidth:
            raise PyrtlError('Conditional assignment only defined on '
                             'WireVectors with pre-defined bitwidths')
        other = self._prepare_for_assignment(other)
        if currently_under_condition():
            _build(self, other)
        else:
            self._build(other)
        return self

    def _two_var_op(self, other, op):
        from .corecircuits import as_wires, match_bitwidth

        # convert constants if necessary
        a, b = self, as_wires(other)
        a, b = match_bitwidth(a, b)
        resultlen = len(a)  # both are the same length now

        # some operations actually create more or less bits
        if op in '+-':
            resultlen += 1  # extra bit required for carry
        elif op == '*':
            resultlen = resultlen * 2  # more bits needed for mult
        elif op in '<>=':
            resultlen = 1

        s = WireVector(bitwidth=resultlen)
        net = LogicNet(
            op=op,
            op_param=None,
            args=(a, b),
            dests=(s,))
        working_block().add_net(net)
        return s

    def __bool__(self):
        """ Use of a wirevector in a statement like "a or b" is forbidden."""
        # python provides no way to overload these logical operations, and thus they
        # are very much not likely to be doing the thing that the programmer would be
        # expecting.
        raise PyrtlError('cannot convert wirevector to compile-time boolean.  This error '
                         'often happens when you attempt to use WireVectors with "==" or '
                         'something that calls "__eq__", such as when you test if a '
                         'wirevector is "in" something')

    __nonzero__ = __bool__  # for Python 2 and 3 compatibility

    def __and__(self, other):
        """ Creates a LogicNet that ands two wires together into a single wire
            :return Wirevector: the result wire of the operation
        """
        return self._two_var_op(other, '&')

    def __rand__(self, other):
        return self._two_var_op(other, '&')

    def __iand__(self, other):
        raise PyrtlError('error, operation not allowed on WireVectors')

    def __or__(self, other):
        """ Creates a LogicNet that ors two wires together into a single wire
            :return Wirevector: the result wire of the operation
        """
        return self._two_var_op(other, '|')

    def __ror__(self, other):
        return self._two_var_op(other, '|')

    # __ior__ used for conditional assignment above

    def __xor__(self, other):
        """ Creates a LogicNet that xors two wires together into a single wire
            :return Wirevector: the result wire of the operation
        """
        return self._two_var_op(other, '^')

    def __rxor__(self, other):
        return self._two_var_op(other, '^')

    def __ixor__(self, other):
        raise PyrtlError('error, operation not allowed on WireVectors')

    def __add__(self, other):
        """ Creates a LogicNet that adds two wires together into a single wirevector.

        :return Wirevector: Returns the result wire of the operation.
          The resulting wire has one more bit than the longer of the two input wires.

        Addition is compatible with two's complement signed numbers.
        """
        return self._two_var_op(other, '+')

    def __radd__(self, other):
        return self._two_var_op(other, '+')

    def __iadd__(self, other):
        raise PyrtlError('error, operation not allowed on WireVectors')

    def __sub__(self, other):
        """ Creates a LogicNet that subtracts the right wire from the left one.

        :return Wirevector: Returns the result wire of the operation.
          The resulting wire has one more bit than the longer of the two input wires.

        Subtraction is compatible with two's complement signed numbers.
        """
        return self._two_var_op(other, '-')

    def __rsub__(self, other):
        from .corecircuits import as_wires
        other = as_wires(other)  # '-' op is not symmetric
        return other._two_var_op(self, '-')

    def __isub__(self, other):
        raise PyrtlError('error, operation not allowed on WireVectors')

    def __mul__(self, other):
        """ Creates a LogicNet that multiplies two different wirevectors.

        :return Wirevector: Returns the result wire of the operation.
          The resulting wire's bitwidth is the sum of the two input wires' bitwidths.

        Multiplication is *not* compatible with two's complement signed numbers.
        """
        return self._two_var_op(other, '*')

    def __rmul__(self, other):
        return self._two_var_op(other, '*')

    def __imul__(self, other):
        raise PyrtlError('error, operation not allowed on WireVectors')

    def __lt__(self, other):
        """ Creates a LogicNet that calculates whether a wire is less than another

        :return Wirevector: a one bit result wire of the operation
        """
        return self._two_var_op(other, '<')

    def __le__(self, other):
        """ Creates LogicNets that calculates whether a wire is less than or equal to another

        :return Wirevector: a one bit result wire of the operation
        """
        return ~ self._two_var_op(other, '>')

    def __eq__(self, other):
        """ Creates a LogicNet that calculates whether a wire is equal to another

        :return Wirevector: a one bit result wire of the operation
        """
        return self._two_var_op(other, '=')

    def __ne__(self, other):
        """ Creates LogicNets that calculates whether a wire not equal to another
        :return Wirevector: a one bit result wire of the operation
        """
        return ~ self._two_var_op(other, '=')

    def __gt__(self, other):
        """ Creates a LogicNet that calculates whether a wire is greater than another
        :return Wirevector: a one bit result wire of the operation
        """
        return self._two_var_op(other, '>')

    def __ge__(self, other):
        """ Creates LogicNets that calculates whether a wire is greater than or equal to another
        :return Wirevector: a one bit result wire of the operation
        """
        return ~ self._two_var_op(other, '<')

    def __invert__(self):
        """ Creates LogicNets that inverts a wire
        :return Wirevector: a result wire for the operation
        """
        outwire = WireVector(bitwidth=len(self))
        net = LogicNet(
            op='~',
            op_param=None,
            args=(self,),
            dests=(outwire,))
        working_block().add_net(net)
        return outwire

    def __getitem__(self, item):
        """ Grabs a subset of the wires
        :return Wirevector: a result wire for the operation
        """
        if self.bitwidth is None:
            raise PyrtlError('You cannot get a subset of a wire with no bitwidth')
        allindex = range(self.bitwidth)
        if isinstance(item, int):
            selectednums = (allindex[item], )  # this method handles negative numbers correctly
        else:  # slice
            selectednums = tuple(allindex[item])
        if not selectednums:
            raise PyrtlError('selection %s must have at least select one wire' % str(item))
        outwire = WireVector(bitwidth=len(selectednums))
        net = LogicNet(
            op='s',
            op_param=selectednums,
            args=(self,),
            dests=(outwire,))
        working_block().add_net(net)
        return outwire

    def __lshift__(self, other):
        raise PyrtlError('Shifting using the << and >> operators are not supported'
                         'in PyRTL.'
                         'If you are trying to select bits in a wire, use'
                         'the indexing operator (wire[indexes]) instead.\n\n'
                         'For example: wire[2:9] selects the wires from index 2 to '
                         'index 8 to make a new length 7 wire. \n\n If you are really '
                         'trying to *execution time* shift you can use "shift_left_arithmetic", '
                         '"shift_right_arithmetic", "shift_left_logical", "shift_right_logical"')

    __rshift__ = __lshift__

    def __mod__(self, other):
        raise PyrtlError("Masking with the % operator is not supported"
                         "in PyRTL. "
                         "Instead if you are trying to select bits in a wire, use"
                         "the indexing operator (wire[indexes]) instead.\n\n"
                         "For example: wire[2:9] selects the wires from index 2 to "
                         "index 8 to make a new length 7 wire.")

    def __len__(self):
        """ Get the bitwidth of a WireVector.

        :return integer: Returns the length (i.e. bitwidth) of the WireVector
           in bits.

        Note that WireVectors do not need to have a bitwidth defined
        when they are first allocated.  They can get it from a <<= assignment
        later.  However, if you check the `len` of WireVector with undefined
        bitwidth it will throw `PyrtlError`.
        """
        if self.bitwidth is None:
            raise PyrtlError('length of wirevector not yet defined')
        else:
            return self.bitwidth

    def __enter__(self):
        """ Use wires as contexts for conditional assignments. """
        from .conditional import _push_condition
        _push_condition(self)

    def __exit__(self, *execinfo):
        from .conditional import _pop_condition
        _pop_condition()

    # more functions for wires
    def nand(self, other):
        """ Creates a LogicNet that bitwise nands two wirevector together to a single wirevector.

        :return WireVector: Returns wirevector of the nand operation.
        """
        return self._two_var_op(other, 'n')

    @property
    def bitmask(self):
        """ A property holding a bitmask of the same length as this WireVector.
        Specifically it is an integer with a number of bits set to 1 equal to the
        bitwidth of the WireVector.

        It is often times useful to "mask" an integer such that it fits in the
        the number of bits of a WireVector.  As a convenience for this, the
        `bitmask` property is provided.  As an example, if there was a 3-bit
        WireVector `a`, a call to  `a.bitmask()` should return 0b111 or 0x7."""
        if "_bitmask" not in self.__dict__:
            self._bitmask = (1 << len(self)) - 1
        return self._bitmask

    def truncate(self, bitwidth):
        """ Generate a new truncated wirevector derived from self.

        :return WireVector: Returns a new WireVector equal to
           the original WireVector but truncated to the specified bitwidth.

        If the bitwidth specified is larger than the bitwidth of self,
        then PyrtlError is thrown.
        """
        if not isinstance(bitwidth, int):
            raise PyrtlError('Can only truncate to an integer number of bits')
        if bitwidth > self.bitwidth:
            raise PyrtlError('Cannot truncate a wirevector to have more bits than it started with')
        return self[:bitwidth]

    def sign_extended(self, bitwidth):
        """ Generate a new sign extended wirevector derived from self.

        :return WireVector: Returns a new WireVector equal to
           the original WireVector sign extended to the specified bitwidth.

        If the bitwidth specified is smaller than the bitwidth of self,
        then PyrtlError is thrown.
        """
        return self._extend_with_bit(bitwidth, self[-1])

    def zero_extended(self, bitwidth):
        """ Generate a new zero extended wirevector derived from self.

        :return WireVector: Returns a new WireVector equal to
           the original WireVector zero extended to the specified bitwidth.

        If the bitwidth specified is smaller than the bitwidth of self,
        then PyrtlError is thrown.
        """
        return self._extend_with_bit(bitwidth, 0)

    def _extend_with_bit(self, bitwidth, extbit):
        numext = bitwidth - self.bitwidth
        if numext == 0:
            return self
        elif numext < 0:
            raise PyrtlError(
                'Neither zero_extended nor sign_extended can'
                ' reduce the number of bits')
        else:
            from .corecircuits import concat
            if isinstance(extbit, int):
                extbit = Const(extbit, bitwidth=1)
            extvector = WireVector(bitwidth=numext)
            net = LogicNet(
                op='s',
                op_param=(0,) * numext,
                args=(extbit,),
                dests=(extvector,))
            working_block().add_net(net)
            return concat(extvector, self)

    def as_bundle(self, obj):
        bundle_bw = Bundle.get_bundle_bitwidth(obj)

        if len(self) != bundle_bw:
            raise PyrtlError(
                "Width of wire %s (%d) does not equal width of bundle %s (%d)"
                % (str(self.name), len(self), str(obj.name), bundle_bw)
            )

        w = Bundle(obj)
        w <<= self
        return w


# -----------------------------------------------------------------------
#  ___     ___  ___       __   ___  __           ___  __  ___  __   __   __
# |__  \_/  |  |__  |\ | |  \ |__  |  \    \  / |__  /  `  |  /  \ |__) /__`
# |___ / \  |  |___ | \| |__/ |___ |__/     \/  |___ \__,  |  \__/ |  \ .__/
#

class Input(WireVector):
    """ A WireVector type denoting inputs to a block (no writers) """
    _code = 'I'

    def __init__(self, bitwidth=None, name='', block=None):
        super(Input, self).__init__(bitwidth=bitwidth, name=name, block=block)

    def __ilshift__(self, _):
        """ This is an illegal op for Inputs. They cannot be assigned to in this way """
        raise PyrtlError(
            'Connection using <<= operator attempted on Input. '
            'Inputs, such as "%s", cannot have values generated internally. '
            "aka they can't have other wires driving it"
            % str(self.name))

    def __ior__(self, _):
        """ This is an illegal op for Inputs. They cannot be assigned to in this way """
        raise PyrtlError(
            'Connection using |= operator attempted on Input. '
            'Inputs, such as "%s", cannot have values generated internally. '
            "aka they can't have other wires driving it"
            % str(self.name))


class Output(WireVector):
    """ A WireVector type denoting outputs of a block (no readers)
    Even though Output seems to have valid ops such as __or__ , using
    them will throw an error.
    """
    _code = 'O'

    def __init__(self, bitwidth=None, name='', block=None):
        super(Output, self).__init__(bitwidth, name, block)


class Const(WireVector):
    """ A WireVector representation of a constant value

    Converts from bool, integer, or verilog-style strings to a constant
    of the specified bitwidth.  If the bitwidth is too short to represent
    the specified constant then an error is raised.  If a possitive
    integer is specified the bitwidth can be infered from the constant.
    If a negative integer is provided in the simulation, it is converted
    to a two's complement representation of the specified bitwidth."""

    _code = 'C'

    def __init__(self, val, bitwidth=None, block=None):
        """ Construct a constant implementation at initialization

        :param int or str val: The value for the const wirevector
        :return: a wirevector object representing a const wire

        Descriptions for all parameters not listed above can be found at
        py:method:: WireVector.__init__()
        """
        self._validate_bitwidth(bitwidth)
        from .helperfuncs import infer_val_and_bitwidth
        num, bitwidth = infer_val_and_bitwidth(val, bitwidth)

        if num < 0:
            raise PyrtlInternalError(
                'Const somehow evaluating to negative integer after checks')
        if (num >> bitwidth) != 0:
            raise PyrtlError(
                'error constant "%s" cannot fit in the specified %d bits'
                % (str(num), bitwidth))

        name = _constIndexer.make_valid_string() + '_' + str(val)

        super(Const, self).__init__(bitwidth=bitwidth, name=name, block=block)
        # add the member "val" to track the value of the constant
        self.val = num

    def __ilshift__(self, other):
        """ This is an illegal op for Consts. Their value is set in the __init__ function"""
        raise PyrtlError(
            'ConstWires, such as "%s", should never be assigned to with <<='
            % str(self.name))

    def __ior__(self, _):
        """ This is an illegal op for Inputs. They cannot be assigned to in this way """
        raise PyrtlError(
            'Connection using |= operator attempted on Const. '
            'ConstWires, such as "%s", cannot have values generated internally. '
            "aka they cannot have other wires driving it"
            % str(self.name))


class Register(WireVector):
    """ A WireVector with a register state element embedded.

    Registers only update their outputs on posedge of an implicit
    clk signal.  The "value" in the current cycle can be accessed
    by just referencing the Register itself.  To set the value for
    the next cycle (after the next posedge) you write to the
    property .next with the <<= operator.  For example, if you want
    to specify a counter it would look like: "a.next <<= a + 1"
    """
    _code = 'R'

    # When the register is called as such:  r.next <<= foo
    # the sequence of actions that happens is:
    # 1) The property .next is called to get the "value" of r.next
    # 2) The "value" is then passed to __ilshift__
    #
    # The resulting behavior should enforce the following:
    # r.next <<= 5  -- good
    # a <<= r       -- good
    # r <<= 5       -- error
    # a <<= r.next  -- error
    # r.next = 5    -- error

    class _Next(object):
        """ This is the type returned by "r.next". """

        def __init__(self, reg):
            self.reg = reg

        def __ilshift__(self, other):
            return self.reg._next_ilshift(other)

        def __ior__(self, other):
            return self.reg._next_ior(other)

        def __bool__(self):
            """ Use of a _next in a statement like "a or b" is forbidden."""
            raise PyrtlError('cannot convert Register.next to compile-time boolean.  This error '
                             'often happens when you attempt to use a Register.next with "==" or '
                             'something that calls "__eq__", such as when you test if a '
                             'Register.next is "in" something')

        __nonzero__ = __bool__  # for Python 2 and 3 compatibility

    class _NextSetter(object):
        """ This is the type returned by __ilshift__ which r.next will be assigned. """

        def __init__(self, rhs, is_conditional):
            self.rhs = rhs
            self.is_conditional = is_conditional

    def __init__(self, bitwidth, name='', block=None):
        super(Register, self).__init__(bitwidth=bitwidth, name=name, block=block)
        self.reg_in = None  # wire vector setting self.next

    @property
    def next(self):
        """
        This property is the way to set what the wirevector will be the next
        cycle (aka, it is before the D-Latch)
        """
        return Register._Next(self)

    def __ilshift__(self, other):
        raise PyrtlError('error, you cannot set registers directly, net .next instead')

    def __ior__(self, other):
        raise PyrtlError('error, you cannot set registers directly, net .next instead')

    def _next_ilshift(self, other):
        from .corecircuits import as_wires
        other = as_wires(other, bitwidth=self.bitwidth)
        if self.bitwidth is None:
            self.bitwidth = other.bitwidth
        return Register._NextSetter(other, is_conditional=False)

    def _next_ior(self, other):
        from .corecircuits import as_wires
        other = as_wires(other, bitwidth=self.bitwidth)
        if not self.bitwidth:
            raise PyrtlError('Conditional assignment only defined on '
                             'Registers with pre-defined bitwidths')
        return Register._NextSetter(other, is_conditional=True)

    @next.setter
    def next(self, nextsetter):
        from .conditional import _build
        if not isinstance(nextsetter, Register._NextSetter):
            raise PyrtlError('error, .next should be set with "<<=" or "|=" operators')
        elif self.reg_in is not None:
            raise PyrtlError('error, .next value should be set once and only once')
        elif nextsetter.is_conditional:
            _build(self, nextsetter.rhs)
        else:
            self._build(nextsetter.rhs)

    def _build(self, next):
        # this actually builds the register which might be from directly setting
        # the property "next" or delayed when there is a conditional assignement
        self.reg_in = next
        net = LogicNet('r', None, args=(self.reg_in,), dests=(self,))
        working_block().add_net(net)


class Bundle(WireVector):
    """ A WireVector whose individual bits are named.

    The initializer takes as its first argument the name of a class whose
    attributes will be interpreted as the names and lengths of fields in a wire.
    The order in which the attributes are defined is important; the first class
    attribute is the MSB of the wire, and the last class attribute of the list is the LSB.

    For example, say there is a wire that represents an instruction. If we wanted to name
    certain segments of bits a certain way, we would create a class with the names and lengths
    of these fields as attributes follows:

        class RFormat:
            funct7 = 7
            rs2 = 5
            rs1 = 5
            funct3 = 3
            rd = 5
            opcode = 7

    Then use it as the argument to Bundle to get back an object whose fields are actually
    wirevectors, accessible by field name:

        w = pyrtl.Bundle(RFormat)
        w <<= 0b00000100110001010000010110010011
        assert sim.inspect(w.funct7) == 0b0000010
        assert sim.inspect(w.rs2) == 0b01100
        assert sim.inspect(w.rs1) == 0b01010
        assert sim.inspect(w.funct3) == 0b000
        assert sim.inspect(w.rd) == 0b01011
        assert sim.inspect(w.opcode) == 0b0010011

    It can be used anywhere a normal wire can be used:

        r = pyrtl.Register(len(w), "r")
        r.next <<= w
        # ...after stepping a few times...
        assert sim.inspect(r) == 0b00000100110001010000010110010011

    And you can interpret other wires as instances of the bundled class, by calling
    `as_bundle`. This does lightweight checks such as making sure that the bundled class
    and the wire you call `as_bundle` on has the same length so that the bits can map properly.
    This allows you to access portions of the wire via fields.

        f7 = r.as_bundle(RFormat).funct7
        assert sim.inspect(f7) == 0b0000010

        y = r.as_bundle(RFormat)
        assert sim.inspect(y.funct7) == 0b0000010
        assert sim.inspect(y.rs2) == 0b01100
        assert sim.inspect(y.rs1) == 0b01010
        assert sim.inspect(y.funct3) == 0b000
        assert sim.inspect(y.rd) == 0b01011
        assert sim.inspect(y.opcode) == 0b0010011

    You can also pass in a list of (field, width) pairs:

        rformat = [("funct7", 7), ("rs2", 5), ("rs1", 5), ("funct3", 3), ("rd", 5), ("opcode", 7)]
        w = pyrtl.Bundle(rformat)

    or an (ordered) dictionary (OrderedDict is the default for Python >= 3.7):

        rformat = {"funct7": 7, "rs2": 5, "rs1": 5, "funct3": 3, "rd": 5, "opcode": 7}
        w = pyrtl.Bundle(rformat)

    instead of a class to form a Bundle. In all forms, order is important.

    In all cases, the 'width' member may actually be a tuple of the form (n, w),
    where n is the actual width and f is a wirevector or function returning
    a wirevector that will be used to define the wire. Otherwise, 'width' should
    just be an integer and will be interpreted as the literal width.
    """
    @staticmethod
    def _get_fields(obj):
        if isinstance(obj, list) and all(map(lambda t: isinstance(t, tuple), obj)):
            # Passed in a list of tuples (i.e. (field, width) pairs), in order from MSB to LSB
            fields = obj
        elif isinstance(obj, dict):
            from collections import OrderedDict
            if (not (sys.version_info[0] >= 3 and sys.version_info[1] >= 7)
               and (not isinstance(obj, OrderedDict))):
                raise PyrtlError("For Python versions < 3.7, the dictionary used to instantiate "
                                 "a Bundle must be explicitly ordered (i.e. OrderedDict)")
            # Assume dictionary stores (field, width) pairs
            fields = list(obj.items())
        elif isinstance(obj, six.class_types):
            if not (sys.version_info[0] >= 3 and sys.version_info[1] >= 7):
                raise PyrtlError("Passing a class as an argument to Bundle() "
                                 "is only allowed for Python versions >= 3.7")
            # Let's assume 'obj' is a **class** name, so treat it as if it has field names.
            # As of Python 3.7, dictionaries preserve insertion order, so a class's attributes
            # (in __dict__) will being ordered as well. This relies on that fact because the
            # fields are defined in MSB to LSB order in the class.
            fs = filter(lambda attr: not attr.startswith("__"), vars(obj))
            fields = [(attr, getattr(obj, attr)) for attr in fs]
        else:
            raise PyrtlError("Cannot determine (field, width) pairs from %s object" % type(obj))
        return fields

    @staticmethod
    def get_bundle_bitwidth(obj):
        fields = Bundle._get_fields(obj)

        def aux(acc, t):
            if isinstance(t[1], tuple):
                width = t[1][0]
            else:
                width = t[1]
            return acc + width
        return reduce(aux, fields, 0)

    def __init__(self, obj, name="", block=None):
        super(Bundle, self).__init__(Bundle.get_bundle_bitwidth(obj), name, block)

        fields = Bundle._get_fields(obj)
        start = 0
        args = []
        for field, length in fields[::-1]:
            if isinstance(length, tuple):
                from .corecircuits import as_wires
                # length is actually a tuple of the form (width, val)
                val = length[1]
                length = length[0]
                if callable(val):
                    val = val()
                val = as_wires(val, bitwidth=length)
                args.append(val)
            setattr(self, field, self[start:start + length])
            start += length

        if args:
            from .corecircuits import concat_list
            self <<= concat_list(args)
