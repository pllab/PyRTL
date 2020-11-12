# pylint: disable=no-member
# pylint: disable=unbalanced-tuple-unpacking

import unittest
import six

import pyrtl
from pyrtl.rtllib import fifos

class TestFifo(unittest.TestCase):
    def setUp(self):
        pyrtl.reset_working_block()

        data_in, valid_in, ready_in, reset = pyrtl.input_list('data_in/8 valid_in/1 ready_in/1 reset/1')
        data_out, valid_out, ready_out = pyrtl.output_list('data_out/8 valid_out/1 ready_out/1')

        f = fifos.Fifo(bitwidth=8, nels=4)

        f.reset <<= reset

        f.data_in <<= data_in
        f.valid_in <<= valid_in
        ready_out <<= f.ready_out

        f.ready_in <<= ready_in
        data_out <<= f.data_out
        valid_out <<= f.valid_out

    def test_fifo_run1(self):
        inputs = {
            'reset':    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            'data_in':  [0, 1, 2, 3, 4, 5, 6, 7, 8, 1, 2, 0, 0, 0],
            'valid_in': [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0],
            'ready_in': [0, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1],
        }

        expected = {
            'data_out':  [0, 0, 1, 2, 3, 4, 4, 5, 6, 7, 8, 1, 2, 7],
            'valid_out': [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0],
            'ready_out': [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        }

        sim = pyrtl.Simulation()
        sim.step_multiple(inputs, expected)

        output = six.StringIO()
        sim.tracer.print_trace(output, compact=True)
        self.assertEqual(output.getvalue(),
            "  data_in 01234567812000\n data_out 00123445678127\n"
            " ready_in 01111011111111\nready_out 11111111111111\n"
            "    reset 10000000000000\n valid_in 01111111111000\n"
            "valid_out 00111111111110\n")

    def test_fifo_run2(self):
        inputs = {
            "reset": "1000000000000000",
            "data_in": "0123456666000000",
            "valid_in": "0111111110000000",
            "ready_in": "0000000100111111",
        }
        expected = {
            "ready_out": "1111100010011111",
            "valid_out": "0011111111111100",
            "data_out": "0011111122234622",
        }

        sim = pyrtl.Simulation()
        sim.step_multiple(inputs, expected)

        output = six.StringIO()
        sim.tracer.print_trace(output, compact=True)
        self.assertEqual(output.getvalue(),
            "  data_in 0123456666000000\n data_out 0011111122234622\n"
            " ready_in 0000000100111111\nready_out 1111100010011111\n"
            "    reset 1000000000000000\n valid_in 0111111110000000\n"
            "valid_out 0011111111111100\n")

if __name__ == "__main__":
    unittest.main()