# pylint: disable=no-member
# pylint: disable=unbalanced-tuple-unpacking

import unittest
import six

import pyrtl
from pyrtl.rtllib import fifos


class TestSimpleModules(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()

    def test_fifo_wire_sorts(self):
        f = fifos.Fifo(8, 4)
        self.assertTrue(isinstance(f.reset.sort, pyrtl.wiresorts.Free))
        self.assertTrue(isinstance(f.valid_in.sort, pyrtl.wiresorts.Free))
        self.assertTrue(isinstance(f.data_in.sort, pyrtl.wiresorts.Free))
        self.assertTrue(isinstance(f.ready_in.sort, pyrtl.wiresorts.Free))

        self.assertTrue(isinstance(f.ready_out.sort, pyrtl.wiresorts.Giving))
        self.assertTrue(isinstance(f.valid_out.sort, pyrtl.wiresorts.Giving))
        self.assertTrue(isinstance(f.data_out.sort, pyrtl.wiresorts.Giving))

    def test_wire_sort_in_module(self):
        class T(pyrtl.Module):
            def __init__(self):
                super(T, self).__init__()

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
        self.assertTrue(isinstance(t.w1.sort, pyrtl.wiresorts.Needed))
        self.assertEqual(t.w1.sort.needed_by_set, {t.w9})
        self.assertTrue(isinstance(t.w2.sort, pyrtl.wiresorts.Free))
        self.assertTrue(isinstance(t.w3.sort, pyrtl.wiresorts.Free))
        self.assertTrue(isinstance(t.w4.sort, pyrtl.wiresorts.Needed))
        self.assertEqual(t.w4.sort.needed_by_set, {t.w9})
        self.assertTrue(isinstance(t.w8.sort, pyrtl.wiresorts.Giving))
        self.assertTrue(isinstance(t.w9.sort, pyrtl.wiresorts.Dependent))
        self.assertEqual(t.w9.sort.depends_on_set, {t.w1, t.w4})


class TestMultipleIntraModules(unittest.TestCase):
    class M(pyrtl.Module):
        def __init__(self, name=""):
            super(TestMultipleIntraModules.M, self).__init__(name=name)

        def definition(self):
            a = self.Input(4, 'a')
            b = self.Output(6, 'b')
            b <<= a * 4

    class N(pyrtl.Module):
        def __init__(self, name=""):
            super(TestMultipleIntraModules.N, self).__init__(name=name)

        def definition(self):
            a = self.Input(10, 'a')
            b = self.Output(10, 'b')
            r = pyrtl.Register(10, 'r')
            r.next <<= a + 1
            b <<= r * 4

    def setUp(self):
        pyrtl.reset_working_block()

    def test_single_connected(self):
        m = TestMultipleIntraModules.M()
        a_in = pyrtl.Input(4, 'a_in')
        b_out = pyrtl.Output(6, 'b_out')
        m.a <<= a_in + 1
        b_out <<= m.b - 1

        sim = pyrtl.Simulation()
        sim.step_multiple({'a_in': [1, 2, 3]}, {'b_out': [7, 11, 15]})

        output = six.StringIO()
        sim.tracer.print_trace(output, compact=True)
        self.assertEqual(output.getvalue(), " a_in 123\nb_out 71115\n")

        self.assertTrue(isinstance(m.a.sort, pyrtl.wiresorts.Needed))
        self.assertTrue(isinstance(m.b.sort, pyrtl.wiresorts.Dependent))
        self.assertEqual(m.a.sort.needed_by_set, {m.b})
        self.assertEqual(m.b.sort.depends_on_set, {m.a})

    def test_simple_connected_to_self_no_loop(self):
        n = TestMultipleIntraModules.N()
        n.a <<= n.b
        out = pyrtl.Output(10, 'out')
        out <<= n.b

        sim = pyrtl.Simulation()
        sim.step_multiple({}, nsteps=5)
        output = six.StringIO()
        sim.tracer.print_trace(output, compact=True)
        self.assertEqual(output.getvalue(), "out 042084340\n  r 0152185\n")

    def test_three_connected_simple_no_cycle_because_state(self):
        n1 = TestMultipleIntraModules.N(name="n1")
        n2 = TestMultipleIntraModules.N(name="n2")
        n3 = TestMultipleIntraModules.N(name="n3")
        n2.a <<= n1.b
        n3.a <<= n2.b
        n1.a <<= n3.b

        self.assertTrue(isinstance(n1.a.sort, pyrtl.wiresorts.Free))
        self.assertEqual(n1.a.sort.needed_by_set, set())
        self.assertTrue(isinstance(n1.b.sort, pyrtl.wiresorts.Giving))
        self.assertFalse(n1.b.sort.depends_on_set, set())

    def test_three_connected_simple_cycle_no_state(self):
        m1 = TestMultipleIntraModules.M()
        m2 = TestMultipleIntraModules.M()
        m3 = TestMultipleIntraModules.M()
        m2.a <<= m1.b
        m3.a <<= m2.b
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            m1.a <<= m3.b
        self.assertTrue(str(ex.exception).startswith("Connection error"))

    def test_ill_connected_to_self_loop(self):
        m = TestMultipleIntraModules.M()

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            m.a <<= m.b
        self.assertTrue(str(ex.exception).startswith("Connection error"))

    def test_ill_connected_transitive_normal_intermediate_wire(self):
        m = TestMultipleIntraModules.M()

        x = m.b * 2
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            m.a <<= x
        self.assertTrue(str(ex.exception).startswith("Connection error"))

    def test_loop_after_many_steps(self):
        """ Tests the scenario where you connect module input to
            something (say X), then connect module output to something
            else (say Y), and then later connect X to Y.
        """

        m = TestMultipleIntraModules.M()
        w1 = pyrtl.WireVector(4)
        m.a <<= w1
        w2 = m.b * 2
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            w1 <<= w2
        self.assertTrue(str(ex.exception).startswith("Connection error"))


class TestNestedModulesNBitAdder(unittest.TestCase):

    class OneBitAdder(pyrtl.Module):
        def __init__(self, name=""):
            super(TestNestedModulesNBitAdder.OneBitAdder, self).__init__(name=name)

        def definition(self):
            a = self.Input(1, 'a')
            b = self.Input(1, 'b')
            cin = self.Input(1, 'cin')
            s = self.Output(1, 's')
            cout = self.Output(1, 'cout')
            s <<= a ^ b ^ cin
            cout <<= (a & b) | (a & cin) | (b & cin)

    class NBitAdder(pyrtl.Module):
        def __init__(self, n, name=""):
            assert (n > 0)
            self.n = n
            super(TestNestedModulesNBitAdder.NBitAdder, self).__init__(name=name)

        def definition(self):
            a = self.Input(self.n, 'a')
            b = self.Input(self.n, 'b')
            cin = self.Input(1, 'cin')
            cout = self.Output(1, 'cout')
            s = self.Output(self.n, 's')

            ss = []
            for i in range(self.n):
                oba = TestNestedModulesNBitAdder.OneBitAdder(name="oba_" + str(i))
                oba.a <<= a[i]
                oba.b <<= b[i]
                oba.cin <<= cin
                ss.append(oba.s)
                cin = oba.cout
            s <<= pyrtl.concat_list(ss)
            cout <<= cin

    def setUp(self):
        pyrtl.reset_working_block()
        self.module = TestNestedModulesNBitAdder.NBitAdder(4, name="nba")

    def test_sort_caching_correct(self):
        # For each submodule, verify the wiresorts are correct, meaning we didn't
        # just copy the sort via caching, but actually got the corresponding io
        # wire for each submodule.
        for oba in self.module.submodules:
            self.assertTrue(isinstance(oba.a.sort, pyrtl.wiresorts.Needed))
            self.assertTrue(oba.a.sort.needed_by_set, {oba.s, oba.cout})
            self.assertTrue(isinstance(oba.b.sort, pyrtl.wiresorts.Needed))
            self.assertTrue(oba.b.sort.needed_by_set, {oba.s, oba.cout})
            self.assertTrue(isinstance(oba.cin.sort, pyrtl.wiresorts.Needed))
            self.assertTrue(oba.cin.sort.needed_by_set, {oba.s, oba.cout})
            self.assertTrue(isinstance(oba.s.sort, pyrtl.wiresorts.Dependent))
            self.assertTrue(oba.s.sort.depends_on_set, {oba.a, oba.b, oba.cin})
            self.assertTrue(isinstance(oba.cout.sort, pyrtl.wiresorts.Dependent))
            self.assertTrue(oba.cout.sort.depends_on_set, {oba.a, oba.b, oba.cin})


class TestNestedModules(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()

    def test_nested_connection_with_state(self):
        class Inner(pyrtl.Module):
            def __init__(self):
                super(Inner, self).__init__()

            def definition(self):
                x = self.Input(6, 'x')
                r = pyrtl.Register(6)
                r.next <<= x
                y = self.Output(7, 'y')
                y <<= r + 4

        class Outer(pyrtl.Module):
            def __init__(self):
                super(Outer, self).__init__()

            def definition(self):
                i = self.Input(6, 'i')
                o = self.Output(7, 'o')
                b = Inner()
                b.x <<= i
                o <<= b.y

        inner_mod = Inner()
        self.assertTrue(isinstance(inner_mod.x.sort, pyrtl.wiresorts.Free))
        self.assertEqual(inner_mod.x.sort.needed_by_set, set())
        self.assertTrue(isinstance(inner_mod.y.sort, pyrtl.wiresorts.Giving))
        self.assertEqual(inner_mod.y.sort.depends_on_set, set())
        outer_mod = Outer()
        self.assertTrue(isinstance(outer_mod.i.sort, pyrtl.wiresorts.Free))
        self.assertEqual(outer_mod.i.sort.needed_by_set, set())
        self.assertTrue(isinstance(outer_mod.o.sort, pyrtl.wiresorts.Giving))
        self.assertEqual(outer_mod.o.sort.depends_on_set, set())

    def test_nested_connection_with_state2(self):
        class Inner(pyrtl.Module):
            def __init__(self, name=""):
                super(Inner, self).__init__(name=name)

            def definition(self):
                w = self.Input(1, 'w')
                x = self.Input(6, 'x')
                r = pyrtl.Register(6)
                r.next <<= x
                y = self.Output(7, 'y')
                y <<= r + 4 + w

        class Outer(pyrtl.Module):
            def __init__(self, name=""):
                super(Outer, self).__init__(name=name)

            def definition(self):
                i = self.Input(6, 'i')
                j = self.Input(1, 'j')
                o = self.Output(7, 'o')
                b = Inner("inner1")
                b.x <<= i
                b.w <<= j
                o <<= b.y

        inner_mod = Inner("inner2")
        self.assertTrue(isinstance(inner_mod.x.sort, pyrtl.wiresorts.Free))
        self.assertEqual(inner_mod.x.sort.needed_by_set, set())
        self.assertTrue(isinstance(inner_mod.w.sort, pyrtl.wiresorts.Needed))
        self.assertEqual(inner_mod.w.sort.needed_by_set, {inner_mod.y})
        self.assertTrue(isinstance(inner_mod.y.sort, pyrtl.wiresorts.Dependent))
        self.assertEqual(inner_mod.y.sort.depends_on_set, {inner_mod.w})
        outer_mod = Outer("outer")
        self.assertTrue(isinstance(outer_mod.i.sort, pyrtl.wiresorts.Free))
        self.assertEqual(outer_mod.i.sort.needed_by_set, set())
        self.assertTrue(isinstance(outer_mod.j.sort, pyrtl.wiresorts.Needed))
        self.assertEqual(outer_mod.j.sort.needed_by_set, {outer_mod.o})
        self.assertTrue(isinstance(outer_mod.o.sort, pyrtl.wiresorts.Dependent))
        self.assertEqual(outer_mod.o.sort.depends_on_set, {outer_mod.j})


if __name__ == "__main__":
    unittest.main()
