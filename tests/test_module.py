# pylint: disable=unbalanced-tuple-unpacking
import pyrtl
import unittest
import pyrtl

class TestBasicModule(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()

    def test_not_externally_connected(self):
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
                # fault occassionally because the ModOutput it reaches doesn't have
                # a 'sort' attribute yet.
                d <<= w + b - 2

        a = A()
        self.assertFalse(a['a'].externally_connected())
        self.assertFalse(a['b'].externally_connected())
    
    def test_attempt_to_access_nonexistent_wire(self):
        class A(pyrtl.Module):
            def __init__(self):
                super().__init__()
            def definition(self):
                pass
        a = A()
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            _ = a['x']
        self.assertEqual(str(ex.exception),
            f"Cannot get non-IO wirevector x from module.\n"
            "Make sure you spelled the wire name correctly, "
            "that you used 'self.Input' and 'self.Output' rather than "
            "'pyrtl.Input' and 'pyrtl.Output' to declare the IO wirevectors, "
            "and that you are accessing them from the correct module."
        )

    # TODO I don't have this check actually happening yet,
    # so for, just don't do the bad thing.
    def _test_bad_output_as_arg(self):
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
                # I think the non-determinism in iterating over sets woudl causes
                # this to fault occassionally because the ModOutput it
                # reaches doesn't have a 'sort' attribute yet.
                d <<= c + b - 2

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            A()
        self.assertEqual(str(ex.exception),
            f"Invalid module. Module output c cannot be "
            "used on the rhs of <<= while within a module definition.")
    
    def test_no_super_call_in_initializer(self):
        class M(pyrtl.Module):
            def __init__(self):
                pass

            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(3, 'o')
                o <<= i + 1

        m = M()
        with self.assertRaises(AttributeError) as ex:
            m['i'].to_pyrtl_input()
        self.assertEqual(str(ex.exception),
            "'M' object has no attribute 'input_dict'"
        )

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
            w <<= m['i']
        self.assertEqual(str(ex.exception),
            "Invalid module. Module output i/2W can only "
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
            m['o'] <<= 3
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
        b['i'] <<= a['o']

        a["ain"].to_pyrtl_input()
        b["bout"].to_pyrtl_output()

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
        # name is hidden behind .original_name, so that
        # they when they write .name, it doesn't give
        # what you would expect. It would be better if
        # .name was opaque/only used internally, and the user
        # only really saw the wire via __str__ calls.
        self.assertEqual(m['i'].original_name, 'i')
        self.assertEqual(m['j'].original_name, 'j')
        self.assertEqual(m['o'].original_name, 'o')

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
        m1['i'].to_pyrtl_input()
        m2['i'].to_pyrtl_input()
        m1['o'].to_pyrtl_output()
        m2['o'].to_pyrtl_output()
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
        m1['i'].to_pyrtl_input('m1_i')
        m2['i'].to_pyrtl_input('m2_i')
        m1['o'].to_pyrtl_output('m1_o')
        m2['o'].to_pyrtl_output('m2_o')

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
                b['x'] <<= i
                # Case: nested mod output to outer mod output
                o <<= b['y']

        a = A()
        f = Nested()

        f['i'] <<= a['o_counter']

        a['a'].to_pyrtl_input()
        a['b'].to_pyrtl_input()
        a['c'].to_pyrtl_input()
        f['o_foo'].to_pyrtl_output()

        inputs = {'a': [1], 'b': [2], 'c': [3]}
        outputs = {'o_foo': [11]}
        sim = pyrtl.Simulation()
        sim.step_multiple(inputs, outputs)
    
    def test_is_wire_connected_to_an_input(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()
            
            def definition(self):
                a = self.Input(4, 'a')
                b = self.Output(4, 'b')
                b <<= a
    
        m = M()
        w1 = pyrtl.WireVector(4)
        self.assertEqual(set(w for w in pyrtl.helpfulness._forward_combinational_reachability(w1)
            if isinstance(w, pyrtl.module.ModInput)), set())
        w2 = w1 * 2
        self.assertEqual(set(w for w in pyrtl.helpfulness._forward_combinational_reachability(w2)
            if isinstance(w, pyrtl.module.ModInput)), set())
        m['a'] <<= w2
        self.assertEqual(set(w for w in pyrtl.helpfulness._forward_combinational_reachability(w1)
            if isinstance(w, pyrtl.module.ModInput)), {m['a']})
        self.assertEqual(set(w for w in pyrtl.helpfulness._forward_combinational_reachability(w2)
            if isinstance(w, pyrtl.module.ModInput)), {m['a']})

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
        self.assertEqual(m['a'].original_name, 'a')
        self.assertEqual(m['b'].original_name, 'b')
        self.assertEqual(m['c'].original_name, 'c')
        self.assertEqual(m['d'].original_name, 'd')
        self.assertTrue(isinstance(m['a'], pyrtl.module.ModInput))
        self.assertTrue(isinstance(m['b'], pyrtl.module.ModInput))
        self.assertTrue(isinstance(m['c'], pyrtl.module.ModOutput))
        self.assertTrue(isinstance(m['d'], pyrtl.module.ModOutput))
        self.assertFalse(m['a'].externally_connected())
        self.assertFalse(m['b'].externally_connected())
        self.assertFalse(m['c'].externally_connected())
        self.assertFalse(m['d'].externally_connected())

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