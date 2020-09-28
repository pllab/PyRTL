# pylint: disable=unbalanced-tuple-unpacking
# pylint: disable=no-member
import pyrtl
import unittest
import pyrtl

class TestBasicModule(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()
    
    def test_no_modules_instantiated(self):
        class _A(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                a = self.Input(3, 'a')
                b = self.Output(3, 'b')
                b <<= a
        
        self.assertEqual(pyrtl.working_block().modules, {})

    def test_empty_name_module_io(self):

        class A(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                _a = self.Input(3, name='')
        
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            A()
        self.assertEqual(str(ex.exception), "Must supply a non-empty name for a module's input/output wire")

    def test_some_unnamed_modules_instantiated(self):
        class A(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                a = self.Input(3, 'a')
                b = self.Output(3, 'b')
                b <<= a
        
        a1 = A()
        a2 = A()
        for name in pyrtl.working_block().modules.keys():
            self.assertTrue(name.startswith('mod_tmp_'))
        self.assertEqual(set(pyrtl.working_block().modules.values()), {a1, a2})
 
    def test_some_named_modules_instantiated(self):
        class A(pyrtl.Module):
            def __init__(self, name=""):
                super().__init__(name)

            def definition(self):
                a = self.Input(3, 'a')
                b = self.Output(3, 'b')
                b <<= a
        
        a1 = A('a1')
        a2 = A('a2')
        self.assertEqual(pyrtl.working_block().modules['a1'], a1)
        self.assertEqual(pyrtl.working_block().modules['a2'], a2)

    def test_not_externally_driven(self):
        class A(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                a = self.Input(3, 'a')
                b = self.Input(4, 'b')
                c = self.Output(4, 'c')
                d = self.Output(3, 'd')
                w = a + 1
                c <<= w
                # Allowing 'd <<= c + b - 2' might be bad because we might not know c's
                # requires_set before we need to check d, so maybe disallow
                # outputs to be arguments to a net (like is done in overall pyrtl).
                # I think the non-determinism in iterating over sets causes this to
                # fault occassionally because the _ModOutput it reaches doesn't have
                # a 'sort' attribute yet.
                d <<= w + b - 2

        a = A()
        self.assertFalse(a.a.is_driven())
        self.assertFalse(a.b.is_driven())
    
    def test_attempt_to_access_nonexistent_wire(self):
        class A(pyrtl.Module):
            def __init__(self):
                super().__init__()
            def definition(self):
                pass
        a = A()
        with self.assertRaises(AttributeError) as ex:
            _ = a.x
        self.assertTrue(str(ex.exception).startswith(
            f"Cannot get non-IO wirevector 'x' from module.\n"
            "Make sure you spelled the wire name correctly, "
            "that you used 'self.Input' and 'self.Output' rather than "
            "'pyrtl.Input' and 'pyrtl.Output' to declare the IO wirevectors, "
            "and that you are accessing them from the correct module."
        ))

    # TODO I don't have this check actually happening yet,
    # so for, just don't do the bad thing.
    def test_bad_output_as_arg(self):
        class A(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                a = self.Input(3, 'a')
                b = self.Input(4, 'b')
                c = self.Output(4, 'c')
                d = self.Output(3, 'd')
                c <<= a + 1
                # Allowing 'd <<= c + b - 2' is treated as bad because we might
                # not know c's requires_set before we need to check d.
                # I think the non-determinism in iterating over sets would cause
                # this to fault occassionally because the _ModOutput it
                # reaches doesn't have a 'sort' attribute yet.
                # This is an artificial restriction, though. Being a little smarter,
                # we could just create a new wire copying the nets that were used
                # to create c.
                d <<= c + b - 2

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            A()
        self.assertEqual(str(ex.exception),
            f"Invalid module. Module output c/4W cannot be "
             "used as destinations to a net within a module definition.")
    
    def test_no_super_call_in_initializer(self):
        class M(pyrtl.Module):
            def __init__(self):
                pass

            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(3, 'o')
                o <<= i + 1

        m = M()
        with self.assertRaises(KeyError) as ex:
            m.i.to_pyrtl_input()
        self.assertEqual(str(ex.exception), "'input_dict'")

    def test_bad_input_assignment_in_module(self):
        class M(pyrtl.Module):
            # Problem: tries to assign to an input within a module
            def __init__(self):
                super().__init__()
            
            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(2, 'o')
                i <<= 3
                o <<= i

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            _ = M()
        self.assertEqual(str(ex.exception),
            f"Invalid module. Module input i/2W cannot be used on the "
             "lhs of <<= while within a module definition."
        )

    def test_bad_output_assignment_in_module(self):
        class M(pyrtl.Module):
            # Problem: tries to assign output to a value within a module
            def __init__(self):
                super().__init__()
            
            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(2, 'o')
                _w = i + 3
                v = pyrtl.WireVector(5)
                v <<= o

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            _ = M()
        self.assertEqual(str(ex.exception),
            f"Invalid module. Module output o/2W cannot be used on the "
            "rhs of <<= while within a module definition."
        )

    def test_not_all_internally_connected(self):
        class M(pyrtl.Module):
            # Problem: not all inputs are connected to internal logic (i.e. unused io)
            def __init__(self):
                super().__init__()
        
            def definition(self):
                # Trivial, because Python will warn about unused variable.
                _i = self.Input(2, 'i')
                o = self.Output(2, 'o')
                o <<= 1

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            _ = M()
        self.assertEqual(str(ex.exception),
            f"Invalid module. Input i/2W is not connected to any internal module logic."
        )

    def test_bad_input_assignment_outside_module(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()
        
            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(4, 'o')
                o <<= i + 2
        
        m = M()
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            w = pyrtl.WireVector(2)
            w <<= m.i
        self.assertEqual(str(ex.exception),
            "Invalid module. Module input i/2W can only "
            "be used on the rhs of <<= while within a module definition.")

    def test_bad_output_assignment_outside_module(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()
        
            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(4, 'o')
                o <<= i + 2
        
        m = M()
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            m.o <<= 3
        self.assertEqual(str(ex.exception),
            "Invalid module. Module output o/4W can only "
            "be used on the lhs of <<= while within a module definition.")

    def test_connect_different_sizes(self):
        class A(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                ain = self.Input(6, 'ain')
                o = self.Output(6, 'o')
                o <<= ain + 3

        class B(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                i = self.Input(5, 'i')
                bout = self.Output(5, 'bout')
                bout <<= i

        a = A()
        b = B()
        b.i <<= a.o

        a.ain.to_pyrtl_input()
        b.bout.to_pyrtl_output()

        inputs = {
            'ain': [11, 10, 9]
        }
        outputs = {
            'bout': [14, 13, 12]
        }

        sim = pyrtl.Simulation()
        sim.step_multiple(inputs, outputs)

    def test_module_io_names(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()
        
            def definition(self):
                i = self.Input(2, 'i')
                j = self.Input(5, 'j')
                o = self.Output(7, 'o')
                o <<= i + 1 * j
        
        m = M()
        # It's a little distasteful that the user-defined
        # name is hidden behind ._original_name, so that
        # they when they write .name, it doesn't give
        # what you would expect. It would be better if
        # .name was opaque/only used internally, and the user
        # only really saw the wire via __str__ calls.
        self.assertEqual(m.i._original_name, 'i')
        self.assertEqual(m.j._original_name, 'j')
        self.assertEqual(m.o._original_name, 'o')

    def test_connect_duplicate_modules_bad(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()
        
            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(3, 'o')
                o <<= i + 1

        m1 = M()
        m2 = M()
        m1.i.to_pyrtl_input()
        m2.i.to_pyrtl_input()
        m1.o.to_pyrtl_output()
        m2.o.to_pyrtl_output()
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            _ = pyrtl.Simulation()
        self.assertTrue(str(ex.exception).startswith(
            "Duplicate wire names found for the following different signals"))

    def test_connect_duplicate_modules_good(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()
        
            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(3, 'o')
                o <<= i + 1

        m1 = M()
        m2 = M()
        m1.i.to_pyrtl_input('m1_i')
        m2.i.to_pyrtl_input('m2_i')
        m1.o.to_pyrtl_output('m1_o')
        m2.o.to_pyrtl_output('m2_o')

        sim = pyrtl.Simulation()
        inputs = {
            'm1_i': [1,2,3,0,1],
            'm2_i': [0,0,1,1,2],
        }
        outputs = {
            'm1_o': [2,3,4,1,2],
            'm2_o': [1,1,2,2,3],
        }
        sim.step_multiple(inputs, outputs)

    def test_good_nested_connection(self):
        class A(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                a = self.Input(2, 'a')
                b = self.Input(2, 'b')
                c = self.Input(2, 'c')
                o = self.Output(5, 'o_counter')
                o <<= a + b * c

        class B(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                x = self.Input(6, 'x')
                y = self.Output(7, 'y')
                y <<= x + 4

        class Nested(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                i = self.Input(6, 'i')
                o = self.Output(7, 'o_foo')
                b = B()
                # Case: outer mod input to nested mod input
                b.x <<= i
                # Case: nested mod output to outer mod output
                o <<= b.y

        a = A()
        f = Nested()

        f.i <<= a.o_counter

        a.a.to_pyrtl_input()
        a.b.to_pyrtl_input()
        a.c.to_pyrtl_input()
        f.o_foo.to_pyrtl_output()

        inputs = {'a': [1], 'b': [2], 'c': [3]}
        outputs = {'o_foo': [11]}
        sim = pyrtl.Simulation()
        sim.step_multiple(inputs, outputs)

    def test_no_modification_outside_definition(self):
        class A(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                a = self.Input(3, 'a')
                b = self.Output(3, 'b')
                b <<= a

        a = A()
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            _c = a.Input(5, 'c')
        self.assertEqual(str(ex.exception),
            "Cannot create a module input outside of its definition")

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            _c = a.Output(5, 'c')
        self.assertEqual(str(ex.exception),
            "Cannot create a module output outside of its definition")

    def _test_access_nested_module(self):
        # TODO
        class Inner(pyrtl.Module):
            def __init__(self,name=""):
                super().__init__(name)

            def definition(self):
                a = self.Input(2, 'a')
                o = self.Output(5, 'o_counter')
                o <<= a + 2 * 2

        class Outer(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                x = self.Input(6, 'x')
                y = self.Output(7, 'y')
                i = Inner('inside_mod')
                i.a <<= x
                y <<= i.o_counter - 1

        m = Outer()
        # TODO Ideally we could access them like "m.inside_mod.a".
        # 1) That would require changing how inner modules are instantiated
        # to be some type of call on the outer module's self reference,
        # so there's a way to register the inner module.
        # 2) Or we could have the inner child module take in an optional
        # parent object, with which it registers, like "i = Inner('inside_mod', self)".
        # That doesn't seem so bad, except it allows you to pass in some non-self
        # object as the second argument, breaking the abstraction entirely.
        # 3) Or we could set a flag that tells us the current surrounding module, if
        # any, and use it to set a module's parent. This would need to take into
        # account the further nestedness that is possible, so a stack that pushes/pops
        # the current parent (kind of like conditional handling in PyRTL). This way
        # would eliminate the need to call "self.Input", instead just calling "Input"
        # (or rather "_ModInput", since "Input" clashes with the already exisintg PyRTL class)
        pyrtl.probe(pyrtl.working_block().modules['inside_mod'].a, 'a_probe')
        m.to_pyrtl_io()
        sim = pyrtl.Simulation()
        x_and_a_vals = [1, 4, 9, 11, 5]
        sim.step_multiple({'x': x_and_a_vals}, {'a_probe': x_and_a_vals})

    def _test_cannot_modify_accessed_nested_module(self):
        # TODO
        pass

    def _test_probe_of_module_io(self):
        # TODO
        pass

    def test_wire_to_io_inside_module_good(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()
            def definition(self):
                instr = self.Input(32, 'instr')
                funct7, rs2, rs1, funct3, rd, opcode = pyrtl.chop(instr, 7, 5, 5, 3, 5, 7)
                self.to_output(funct7, 'funct7')
                self.to_output(rs2, 'rs2')
                self.to_output(rs1, 'rs1')
                self.to_output(funct3, 'funct3')
                self.to_output(rd, 'rd')
                self.to_output(opcode, 'opcode')
        m = M()
        self.assertEqual(m.inputs, {m.instr})
        self.assertEqual(m.outputs, {
            m.funct7, m.rs2, m.rs1,
            m.funct3, m.rd, m.opcode
        })

    def test_wire_to_io_inside_module_bad1(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()
            def definition(self):
                w = pyrtl.WireVector(4)
                self.to_output(w)

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            M()
        self.assertTrue(str(ex.exception).startswith("Trying to use the internal name of a wire"))

    def test_wire_to_io_inside_module_bad2(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()
            def definition(self):
                w = pyrtl.WireVector(4)
                self.to_input(w)

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            M()
        self.assertTrue(str(ex.exception).startswith("Trying to use the internal name of a wire"))

    def test_wire_to_io_outside_module_bad(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()
            def definition(self):
                a = self.Input(8, 'a')
                b = self.Output(8, 'b')
                b <<= a

        m = M()

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            w = pyrtl.WireVector(8, 'w')
            m.to_input(w)
        self.assertEqual(str(ex.exception), "Cannot promote a wire to a module input outside of a module's definition")

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            w = pyrtl.WireVector(8, 'w')
            m.to_output(w)
        self.assertEqual(str(ex.exception), "Cannot promote a wire to a module output outside of a module's definition")

    def test_strict_sizing_from_outside(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()
            def definition(self):
                a = self.Input(8, 'a', strict=True)
                b = self.Output(8, 'b')
                b <<= a

        m = M()

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            w = pyrtl.WireVector(7, 'w')
            m.a <<= w
        self.assertEqual(str(ex.exception),
            f"Length of module input {str(m.a)} != length of {str(w)}, "
             "and this module input has strict sizing set to True")

    def test_connect_to_input_twice_from_outside(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()
            def definition(self):
                a = self.Input(8, 'a', strict=True)
                b = self.Output(8, 'b')
                b <<= a + 1

        m = M()

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            w = pyrtl.WireVector(8, 'w')
            y = pyrtl.WireVector(8, 'y')
            m.a <<= w
            m.a <<= y
        self.assertEqual(str(ex.exception),
            f"Attempted to connect to already-connected module input {str(m.a)})")

    def test_connect_to_output_twice_from_inside(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()
            def definition(self):
                a = self.Input(8, 'a', strict=True)
                b = self.Output(8, 'b')
                b <<= a + 1
                b <<= pyrtl.Const(4)

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            M()
        self.assertTrue(str(ex.exception).startswith(
            "Attempted to connect to already-connected module output"))


class TestModuleImport(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()
    
    def test_module_from_working_block(self):
        a = pyrtl.Input(3, 'a')
        b = pyrtl.Input(4, 'b')
        c = pyrtl.Output(4, 'c')
        d = pyrtl.Output(3, 'd')
        r = pyrtl.Register(3)
        e = a * b
        f = e | (a & b)
        c <<= f + 1
        r.next <<= f + 2
        d <<= r

        m = pyrtl.module_from_block()
        self.assertEqual(m.a._original_name, 'a')
        self.assertEqual(m.b._original_name, 'b')
        self.assertEqual(m.c._original_name, 'c')
        self.assertEqual(m.d._original_name, 'd')
        self.assertTrue(isinstance(m.a, pyrtl.module._ModInput))
        self.assertTrue(isinstance(m.b, pyrtl.module._ModInput))
        self.assertTrue(isinstance(m.c, pyrtl.module._ModOutput))
        self.assertTrue(isinstance(m.d, pyrtl.module._ModOutput))
        self.assertFalse(m.a.is_driven())
        self.assertFalse(m.b.is_driven())
        self.assertFalse(m.c.is_driving())
        self.assertFalse(m.d.is_driving())

        m.to_pyrtl_io()
        sim = pyrtl.Simulation()
        inputs = {
            'a': [1, 4, 6, 2],
            'b': [0, 3, 2, 1],
        }
        outputs = {
            'c': [1, 13, 15, 3],
            'd': [0, 2, 6, 0],
        }
        sim.step_multiple(inputs, outputs)

if __name__ == "__main__":
    unittest.main()