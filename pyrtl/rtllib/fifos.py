import pyrtl


class Fifo(pyrtl.Module):
    def __init__(self, bitwidth, nels):
        self.bitwidth = bitwidth
        self.nels = nels
        super().__init__()

    def definition(self):
        ######################
        # I/O
        ######################
        reset = self.Input(1, 'reset')
        ready_in = self.Input(1, 'ready_in')
        valid_in = self.Input(1, 'valid_in')
        ready_out = self.Output(1, 'ready_out')
        valid_out = self.Output(1, 'valid_out')
        data_in = self.Input(self.bitwidth, 'data_in')
        data_out = self.Output(self.bitwidth, 'data_out')

        ######################
        # Internal state
        ######################
        bw = len(pyrtl.as_wires(self.nels))
        queue = pyrtl.MemBlock(self.bitwidth, bw)
        count = pyrtl.Register(bw + 1)
        read_ix, write_ix = pyrtl.Register(bw), pyrtl.Register(bw)

        ######################
        # Combinational logic
        ######################
        ready_out <<= count < self.nels
        valid_out <<= count > 0

        enqueue = ready_out & valid_in
        dequeue = valid_out & ready_in
        data_out <<= queue[read_ix]

        ######################
        # Sequential logic
        ######################
        # Enqueue new data
        with pyrtl.conditional_assignment:
            with enqueue & ~reset:
                queue[write_ix] |= data_in
        # Update read index
        with pyrtl.conditional_assignment:
            with reset:
                read_ix.next |= 0
            with dequeue:
                with read_ix == self.nels - 1:
                    read_ix.next |= 0
                with pyrtl.otherwise:
                    read_ix.next |= read_ix + 1
        # Update write index
        with pyrtl.conditional_assignment:
            with reset:
                write_ix.next |= 0
            with enqueue:
                with write_ix == self.nels - 1:
                    write_ix.next |= 0
                with pyrtl.otherwise:
                    write_ix.next |= write_ix + 1
        # Update count
        with pyrtl.conditional_assignment:
            with reset:
                count.next |= 0
            with enqueue & ~dequeue:
                count.next |= count + 1
            with dequeue & ~enqueue:
                count.next |= count - 1
