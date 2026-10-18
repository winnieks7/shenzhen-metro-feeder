"""Small analytic witnesses for direction, looping chainage, and polygon area."""
import unittest
import numpy as np
from shapely.geometry import Point
from shapely import union_all
from prepare_network import match_monotone
from coverage_analysis import accessible_indices


class GeometryWitness(unittest.TestCase):
    def test_directions_budget_and_no_self(self):
        chain=np.array([0.,100.,250.,400.])
        self.assertEqual(accessible_indices(chain,[2],200,'inbound').tolist(),[1])
        self.assertEqual(accessible_indices(chain,[2],200,'outbound').tolist(),[3])
        self.assertEqual(accessible_indices(chain,[0],500,'inbound').tolist(),[])

    def test_loop_returns_to_terminus_at_end(self):
        xy=np.array([[0.,0.],[100.,0.],[100.,100.],[0.,100.],[0.,0.]])
        result=match_monotone(xy,xy,10)
        np.testing.assert_allclose(result[0],[0,100,200,300,400])
        self.assertEqual(accessible_indices(result[0],[3],150,'outbound').tolist(),[4])

    def test_projection_uses_geometry_not_chords(self):
        xy=np.array([[0.,0.],[100.,0.],[100.,100.]])
        result=match_monotone(xy,np.array([[0.,0.],[100.,100.]]),2)
        self.assertAlmostEqual(result[0][1]-result[0][0],200)

    def test_invalid_sequence_cannot_match(self):
        line=np.array([[0.,0.],[100.,0.]])
        self.assertIsNone(match_monotone(line,np.array([[80.,0.],[20.,0.]]),1))

    def test_identical_and_disjoint_cover(self):
        a=Point(0,0).buffer(10,quad_segs=32);b=Point(30,0).buffer(10,quad_segs=32)
        self.assertAlmostEqual(1-union_all([a,a]).area/(2*a.area),.5)
        self.assertAlmostEqual(1-union_all([a,b]).area/(a.area+b.area),0)
        self.assertAlmostEqual(a.difference(b).area,a.area)


if __name__=='__main__':unittest.main()
