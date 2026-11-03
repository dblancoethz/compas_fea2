import unittest

from compas_fea2.model.nodes import Node
from compas_fea2.results import DisplacementResult
from compas_fea2.results import ReactionResult


class TestNodeResult(unittest.TestCase):
    def test_rotations_from_database_names(self):
        # The results database stores rotations as rx, ry, rz: they must not be dropped.
        node = Node([0, 0, 0])
        r = DisplacementResult(node, x=1.0, y=2.0, z=3.0, rx=0.1, ry=0.2, rz=0.3)
        self.assertEqual((r.x, r.y, r.z), (1.0, 2.0, 3.0))
        self.assertEqual((r.xx, r.yy, r.zz), (0.1, 0.2, 0.3))

    def test_rotations_from_xx_names(self):
        node = Node([0, 0, 0])
        r = ReactionResult(node, x=1.0, y=2.0, z=3.0, xx=4.0, yy=5.0, zz=6.0)
        self.assertEqual((r.xx, r.yy, r.zz), (4.0, 5.0, 6.0))


class TestSetBackend(unittest.TestCase):
    def test_missing_plugin_raises(self):
        import compas_fea2

        previous = compas_fea2.BACKEND
        with self.assertRaises(ImportError):
            compas_fea2.set_backend("compas_fea2_this_plugin_does_not_exist")
        # a failed call must not change the active backend
        self.assertEqual(compas_fea2.BACKEND, previous)


if __name__ == "__main__":
    unittest.main()
