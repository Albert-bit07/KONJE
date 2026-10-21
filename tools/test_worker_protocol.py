import unittest
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


if __name__ == '__main__':
    unittest.main()