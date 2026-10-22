import unittest
import random
from worker_protocol import read_burst


def encode(frames):
    return b'KONJE1' + bytes([len(frames)]) + b''.join(
        len(f).to_bytes(4, 'little') + f for f in frames)


class BurstProtocolTests(unittest.TestCase):
    def test_valid_single_and_burst(self):
        frames = [b'\xff\xd8ab\xff\xd9', b'\xff\xd8cd\xff\xd9', b'\xff\xd8ef\xff\xd9']
        self.assertEqual(read_burst(encode(frames)), frames)
        self.assertEqual(read_burst(encode(frames[:1])), frames[:1])

    def test_corruption_and_excess(self):
        good = encode([b'\xff\xd8ab\xff\xd9'])
        for bad in [good[:-1], good + b'X', b'NO' + good, b'KONJE1\x00',
                    encode([b'FAKE00']), encode([b'\xff\xd8ab\xff\xd9']*4)]:
            with self.subTest(bad=bad[:20]):
                with self.assertRaises(ValueError):
                    read_burst(bad)

    def test_deterministic_malformed_input_corpus(self):
        randomizer = random.Random(20261022)
        frames = [b'\\xff\\xd8' + b'x' * 32 + b'\\xff\\xd9']
        good = encode(frames)
        for index in range(256):
            raw = bytearray(good)
            operation = index % 4
            if operation == 0:
                raw = raw[:randomizer.randrange(len(raw))]
            elif operation == 1:
                raw.extend(bytes([randomizer.randrange(256)]))
            elif operation == 2:
                raw[6] = 0 if (index // 4) % 2 == 0 else 4
            else:
                raw[7:11] = (0xffffffff).to_bytes(4, 'little')
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    read_burst(bytes(raw))

    def test_maximum_declared_length_never_overreads(self):
        header = b'KONJE1\\x01' + (4 * 1024 * 1024).to_bytes(4, 'little')
        with self.assertRaises(ValueError):
            read_burst(header + b'\\xff\\xd8\\xff\\xd9')


if __name__ == '__main__':
    unittest.main()