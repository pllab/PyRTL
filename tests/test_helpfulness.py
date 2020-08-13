# pylint: disable=no-member
import unittest
import pyrtl

class TestHelpfulness(unittest.TestCase):
    class M(pyrtl.Module):
        def __init__(self, name=""):
            super().__init__(name=name)

        def definition(self):
            a = self.Input(4, 'a')
            b = self.Output(6, 'b')
            b <<= a * 4

    class N(pyrtl.Module):
        def __init__(self, name=""):
            super().__init__(name=name)

        def definition(self):
            a = self.Input(4, 'a')
            b = self.Output(6, 'b')
            r = pyrtl.Register(5, 'r')
            r.next <<= a + 1
            b <<= r * 4

    def setUp(self):
        pyrtl.reset_working_block()

    def test_reachability_no_module(self):
        r = pyrtl.Register(1, 'r')
        w1 = pyrtl.WireVector(1, 'w1')
        w2 = pyrtl.WireVector(1, 'w2')
        w3 = pyrtl.WireVector(1, 'w3')
        w4 = pyrtl.WireVector(1, 'w4')
        w5 = w1 & w2
        w10 = pyrtl.Const(0)
        r.next <<= w5 | w3
        w8 = r ^ w10
        w6 = ~w4
        w7 = r ^ w6
        w9 = w7 | w1

        # Backward combinational reachability
        for w in (w1, w2, w3, w4):
            self.assertEqual(pyrtl.helpfulness._backward_combinational_reachability(w), set())
        self.assertEqual(pyrtl.helpfulness._backward_combinational_reachability(w5), {w1, w2})
        self.assertEqual(pyrtl.helpfulness._backward_combinational_reachability(w6), {w4})
        self.assertEqual(pyrtl.helpfulness._backward_combinational_reachability(w7), {r, w6, w4})
        self.assertEqual(pyrtl.helpfulness._backward_combinational_reachability(w8), {r, w10})
        self.assertEqual(pyrtl.helpfulness._backward_combinational_reachability(w9), {r, w7, w6, w4, w1})

        # Forward combinational reachability
        # NOTE: despite me trying not to, some intermediate wires have been automatically
        # created, so we'll do superset comparison for some of these.
        self.assertTrue(pyrtl.helpfulness._forward_combinational_reachability(w1).issuperset({w5, r, w9}))
        self.assertTrue(pyrtl.helpfulness._forward_combinational_reachability(w2).issuperset({w5, r}))
        self.assertTrue(pyrtl.helpfulness._forward_combinational_reachability(w3).issuperset({r}))
        self.assertEqual(pyrtl.helpfulness._forward_combinational_reachability(w4), {w6, w7, w9})
        self.assertTrue(pyrtl.helpfulness._forward_combinational_reachability(w5).issuperset({r}))
        self.assertEqual(pyrtl.helpfulness._forward_combinational_reachability(w6), {w7, w9})
        self.assertEqual(pyrtl.helpfulness._forward_combinational_reachability(w8), set())
        self.assertEqual(pyrtl.helpfulness._forward_combinational_reachability(w9), set())

    def test_wire_sort_in_module(self):
        class T(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                r = pyrtl.Register(1, 'r')
                w1 = self.Input(1, 'w1')
                w2 = self.Input(1, 'w2')
                w3 = self.Input(1, 'w3')
                w4 = self.Input(1, 'w4')
                w8 = self.Output(1, 'w8')
                w9 = self.Output(1, 'w9')
                w5 = w1 & w2
                w10 = pyrtl.Const(0)
                r.next <<= w5 | w3
                w8 <<= r ^ w10
                w6 = ~w4
                w7 = r ^ w6
                w9 <<= w7 | w1

        t = T()
        self.assertTrue(isinstance(t.w1.sort, pyrtl.helpfulness.Needed))
        self.assertEqual(t.w1.sort.awaited_by_set, {t.w9})
        self.assertTrue(isinstance(t.w2.sort, pyrtl.helpfulness.Free))
        self.assertTrue(isinstance(t.w3.sort, pyrtl.helpfulness.Free))
        self.assertTrue(isinstance(t.w4.sort, pyrtl.helpfulness.Needed))
        self.assertEqual(t.w4.sort.awaited_by_set, {t.w9})
        self.assertTrue(isinstance(t.w8.sort, pyrtl.helpfulness.Giving))
        self.assertTrue(isinstance(t.w9.sort, pyrtl.helpfulness.Dependent))
        self.assertEqual(t.w9.sort.requires_set, {t.w1, t.w4})

    def test_single_connected(self):
        m = TestHelpfulness.M()
        a_in = pyrtl.Input(4, 'a_in')
        b_out = pyrtl.Output(6, 'b_out')
        m.a <<= a_in + 1
        b_out <<= m.b - 1

        sim = pyrtl.Simulation()
        sim.step_multiple({'a_in': [1,2,3]}, {'b_out': [7, 11, 15]})
        self.assertTrue(isinstance(m.a.sort, pyrtl.helpfulness.Needed))
        self.assertTrue(isinstance(m.b.sort, pyrtl.helpfulness.Dependent))
        self.assertEqual(m.a.sort.awaited_by_set, {m.b})
        self.assertEqual(m.b.sort.requires_set, {m.a})
    
    def test_three_connected_simple_cycle_no_state(self):
        m1 = TestHelpfulness.M(name="m1")
        m2 = TestHelpfulness.M(name="m2")
        m3 = TestHelpfulness.M(name="m3")
        m2.a <<= m1.b
        m3.a <<= m2.b
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            m1.a <<= m3.b
        self.assertTrue(str(ex.exception).startswith("Connection error!"))

    def test_three_connected_no_simple_because_state(self):
        n1 = TestHelpfulness.N(name="n1")
        n2 = TestHelpfulness.N(name="n2")
        n3 = TestHelpfulness.N(name="n3")
        n2.a <<= n1.b
        n3.a <<= n2.b
        n1.a <<= n3.b

        self.assertTrue(isinstance(n1.a.sort, pyrtl.helpfulness.Free))
        self.assertFalse(n1.a.sort.awaited_by_set)
        self.assertTrue(isinstance(n1.b.sort, pyrtl.helpfulness.Giving))
        self.assertFalse(n1.b.sort.requires_set)

    def test_ill_connected(self):
        m = TestHelpfulness.M()

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            m.a <<= m.b
        self.assertTrue(str(ex.exception).startswith("Connection error!"))

    def test_ill_connected_transitive(self):
        m = TestHelpfulness.M()

        x = m.b * 2
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            m.a <<= x
        self.assertTrue(str(ex.exception).startswith("Connection error!"))

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
        self.assertTrue(isinstance(m.a.sort, pyrtl.helpfulness.Needed))
        self.assertEqual(m.a.sort.awaited_by_set, {m.c})
        self.assertTrue(isinstance(m.b.sort, pyrtl.helpfulness.Needed))
        self.assertEqual(m.b.sort.awaited_by_set, {m.c})
        self.assertTrue(isinstance(m.c.sort, pyrtl.helpfulness.Dependent))
        self.assertEqual(m.c.sort.requires_set, {m.a, m.b})
        self.assertTrue(isinstance(m.d.sort, pyrtl.helpfulness.Giving))
        self.assertFalse(m.d.sort.requires_set)
    
    def test_direct_loop_inner_module(self):
        class Inner(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                x = self.Input(2, 'x')
                y = self.Output(2, 'y')
                y <<= x + 1
        
        class Outer(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                i = Inner()
                i.x <<= i.y
        
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            Outer()
            self.assertTrue(str(ex.exception).startswith("Connection error!"))

    def test_indirect_loop_inner_module(self):
        class Inner(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                x = self.Input(2, 'x')
                y = self.Output(2, 'y')
                y <<= x + 1
        
        class Outer(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                i = Inner()
                w1 = pyrtl.WireVector(2)
                w2 = pyrtl.WireVector(2)
                w1 <<= i.y
                i.x <<= w2
                w2 <<= w1
        
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            Outer()
            self.assertTrue(str(ex.exception).startswith("Connection error!"))

    def test_nested_connection(self):
        class Inner(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                x = self.Input(6, 'x')
                y = self.Output(7, 'y')
                y <<= x + 4

        class Outer(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                i = self.Input(6, 'i')
                o = self.Output(7, 'o_foo')
                b = Inner()
                # Case: outer mod input to nested mod input
                b.x <<= i
                # Case: nested mod output to outer mod output
                o <<= b.y

        i = Inner()
        self.assertTrue(isinstance(i.x.sort, pyrtl.helpfulness.Needed))
        self.assertEqual(i.x.sort.awaited_by_set, {i.y})
        self.assertTrue(isinstance(i.y.sort, pyrtl.helpfulness.Dependent))
        self.assertEqual(i.y.sort.requires_set, {i.x})
        o = Outer()
        self.assertTrue(isinstance(o.i.sort, pyrtl.helpfulness.Needed))
        self.assertEqual(o.i.sort.awaited_by_set, {o.o_foo})
        self.assertTrue(isinstance(o.o_foo.sort, pyrtl.helpfulness.Dependent))
        self.assertEqual(o.o_foo.sort.requires_set, {o.i})

    def test_loop_after_many_steps(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()
            
            def definition(self):
                a = self.Input(4, 'a')
                b = self.Output(4, 'b')
                b <<= a + 1
                
        # Tests the scenario where you connect
        # module input to something (say X), then
        # connect module output to something else (say Y),
        # and then later connect X to Y.

        m = M()
        w1 = pyrtl.WireVector(4)
        m.a <<= w1
        w2 = m.b * 2
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            w1 <<= w2
        self.assertTrue(str(ex.exception).startswith("Connection error!"))

    def test_nested_connection_with_state(self):
        class Inner(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                x = self.Input(6, 'x')
                r = pyrtl.Register(6)
                r.next <<= x
                y = self.Output(7, 'y')
                y <<= r + 4

        class Outer(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                i = self.Input(6, 'i')
                o = self.Output(7, 'o_foo')
                b = Inner()
                b.x <<= i
                o <<= b.y

        i = Inner()
        self.assertTrue(isinstance(i.x.sort, pyrtl.helpfulness.Free))
        self.assertFalse(i.x.sort.awaited_by_set)
        self.assertTrue(isinstance(i.y.sort, pyrtl.helpfulness.Giving))
        self.assertFalse(i.y.sort.requires_set)
        o = Outer()
        self.assertTrue(isinstance(o.i.sort, pyrtl.helpfulness.Free))
        self.assertFalse(o.i.sort.awaited_by_set)
        self.assertTrue(isinstance(o.o_foo.sort, pyrtl.helpfulness.Giving))
        self.assertFalse(o.o_foo.sort.requires_set)

    def test_nested_connection_with_state2(self):
        class Inner(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                w = self.Input(1, 'w')
                x = self.Input(6, 'x')
                r = pyrtl.Register(6)
                r.next <<= x
                y = self.Output(7, 'y')
                y <<= r + 4 + w

        class Outer(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                i = self.Input(6, 'i')
                j = self.Input(1, 'j')
                o = self.Output(7, 'o_foo')
                b = Inner()
                b.x <<= i
                b.w <<= j
                o <<= b.y

        i = Inner()
        self.assertTrue(isinstance(i.x.sort, pyrtl.helpfulness.Free))
        self.assertFalse(i.x.sort.awaited_by_set)
        self.assertTrue(isinstance(i.y.sort, pyrtl.helpfulness.Dependent))
        self.assertEqual(i.y.sort.requires_set, {i.w})
        o = Outer()
        self.assertTrue(isinstance(o.i.sort, pyrtl.helpfulness.Free))
        self.assertFalse(o.i.sort.awaited_by_set)
        self.assertTrue(isinstance(o.j.sort, pyrtl.helpfulness.Needed))
        self.assertEqual(o.j.sort.awaited_by_set, {o.o_foo})
        self.assertTrue(isinstance(o.o_foo.sort, pyrtl.helpfulness.Dependent))
        self.assertEqual(o.o_foo.sort.requires_set, {o.j})

    def test_simple_async_reg_file(self):
        class RegisterFile(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                readreg = self.Input(5, 'readreg')
                writereg = self.Input(5, 'writereg')
                writedata = self.Input(32, 'writedata')
                wen = self.Input(1, 'wen')

                readdata = self.Output(32, 'readdata')

                # Read async, write sync
                rf = pyrtl.MemBlock(bitwidth=32, addrwidth=32, asynchronous=True, name="rf")
                readdata <<= rf[readreg]
                rf[writereg] <<= pyrtl.MemBlock.EnabledWrite(writedata, wen & (writereg != 0))

        # TODO This will probably need to change when if I update how memory blocks
        # are handled in the helpfulness annotator.
        rf = RegisterFile()
        self.assertTrue(isinstance(rf.readreg.sort, pyrtl.helpfulness.Needed))
        self.assertEqual(rf.readreg.sort.awaited_by_set, {rf.readdata})
        self.assertTrue(isinstance(rf.writereg.sort, pyrtl.helpfulness.Free))
        self.assertFalse(rf.writereg.sort.awaited_by_set)
        self.assertTrue(isinstance(rf.writedata.sort, pyrtl.helpfulness.Free))
        self.assertFalse(rf.writedata.sort.awaited_by_set)
        self.assertTrue(isinstance(rf.wen.sort, pyrtl.helpfulness.Free))
        self.assertFalse(rf.wen.sort.awaited_by_set)

        self.assertTrue(isinstance(rf.readdata.sort, pyrtl.helpfulness.Dependent))
        self.assertEqual(rf.readdata.sort.requires_set, {rf.readreg})

    def test_outputs_to_multiple_connections(self):
        class M(pyrtl.Module):
            def __init__(self, name=""):
                super().__init__(name=name)

            def definition(self):
                a = self.Input(4, 'a')
                b = self.Input(6, 'b')
                c = self.Output(6, 'c')
                c <<= a * 4 - b
        m = M()
        w1 = m.c * 4
        w2 = m.c + 2
        r = pyrtl.Register(8)
        r.next <<= w1
        m.a <<= r
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            m.b <<= w2
        self.assertTrue(str(ex.exception).startswith("Connection error!"))

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
        m.a <<= w2
        self.assertEqual(set(w for w in pyrtl.helpfulness._forward_combinational_reachability(w1)
            if isinstance(w, pyrtl.module.ModInput)), {m.a})
        self.assertEqual(set(w for w in pyrtl.helpfulness._forward_combinational_reachability(w2)
            if isinstance(w, pyrtl.module.ModInput)), {m.a})

    def test_is_wire_connected_to_inputs_transitive(self):
        class L(pyrtl.Module):
            def __init__(self):
                super().__init__()
            
            def definition(self):
                a = self.Input(4, 'a')
                b = self.Input(4, 'b')
                c = self.Output(4, 'c')
                r = pyrtl.Register(4)
                c <<= a + 1
                r.next <<= b

        l = L()
        m = TestHelpfulness.M()
        w1 = pyrtl.WireVector(4)
        l.a <<= w1
        w2 = l.c * 2
        m.a <<= w2
        self.assertEqual(set(w for w in pyrtl.helpfulness._forward_combinational_reachability(w1, transitive=True)
            if isinstance(w, pyrtl.module.ModInput)), {l.a, m.a})
        self.assertEqual(set(w for w in pyrtl.helpfulness._forward_combinational_reachability(w1)
            if isinstance(w, pyrtl.module.ModInput)), {l.a})
        self.assertEqual(set(w for w in pyrtl.helpfulness._forward_combinational_reachability(w2)
            if isinstance(w, pyrtl.module.ModInput)), {m.a})

    def test_is_wire_connected_to_outputs_transitive(self):
        class L(pyrtl.Module):
            def __init__(self):
                super().__init__()
            
            def definition(self):
                a = self.Input(4, 'a')
                b = self.Input(4, 'b')
                c = self.Output(4, 'c')
                r = pyrtl.Register(4)
                c <<= a + 1
                r.next <<= b

        l = L()
        m = TestHelpfulness.M()
        w1 = pyrtl.WireVector(4)
        l.a <<= w1
        w2 = l.c * 2
        w1 <<= m.b
        self.assertEqual(set(w for w in pyrtl.helpfulness._backward_combinational_reachability(w2, transitive=True)
            if isinstance(w, pyrtl.module.ModOutput)), {l.c, m.b})
        self.assertEqual(set(w for w in pyrtl.helpfulness._backward_combinational_reachability(w2)
            if isinstance(w, pyrtl.module.ModOutput)), {l.c})
    
    def test_good_sort_ascriptions(self):
        class L(pyrtl.Module):
            def __init__(self, name=""):
                super().__init__(name=name)

            def definition(self):
                a = self.Input(4, 'a', sort=pyrtl.helpfulness.Free)
                b = self.Output(6, 'b', sort=pyrtl.helpfulness.Giving)
                c = self.Input(2, 'c', sort=pyrtl.helpfulness.Needed)
                d = self.Output(2, 'd', sort=pyrtl.helpfulness.Dependent)
                r = pyrtl.Register(5, 'r')
                r.next <<= a + 1
                b <<= r * 4
                d <<= c - 1
        
        L()

    def test_bad_sort_ascriptions(self):
        class L(pyrtl.Module):
            def __init__(self, name=""):
                super().__init__(name=name)

            def definition(self):
                a = self.Input(4, 'a', sort=pyrtl.helpfulness.Needed)
                b = self.Output(6, 'b', sort=pyrtl.helpfulness.Giving)
                c = self.Input(2, 'c', sort=pyrtl.helpfulness.Needed)
                d = self.Output(2, 'd', sort=pyrtl.helpfulness.Dependent)
                r = pyrtl.Register(5, 'r')
                r.next <<= a + 1
                b <<= r * 4
                d <<= c - 1
        
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            L()
        self.assertEqual(str(ex.exception),
            "Unmatched sort ascription on wire a/4W.\n"
            "User provided Needed\n"
            "But computed Free")

    def test_invalid_input_sort_ascription(self):
        class L(pyrtl.Module):
            def __init__(self, name=""):
                super().__init__(name=name)

            def definition(self):
                a = self.Input(4, 'a', sort=pyrtl.helpfulness.Dependent)
                b = self.Output(6, 'b', sort=pyrtl.helpfulness.Dependent)
                b <<= r * 4
        
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            L()
        self.assertEqual(str(ex.exception),
            ("Invalid sort ascription for input a "
             "(must provide either Free or Needed)"))

    def test_invalid_output_sort_ascription(self):
        class L(pyrtl.Module):
            def __init__(self, name=""):
                super().__init__(name=name)

            def definition(self):
                a = self.Input(4, 'a', sort=pyrtl.helpfulness.Needed)
                b = self.Output(6, 'b', sort=pyrtl.helpfulness.Needed)
                b <<= r * 4
        
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            L()
        self.assertEqual(str(ex.exception),
            ("Invalid sort ascription for output b "
             "(must provide either Giving or Dependent)"))

if __name__ == '__main__':
    unittest.main()