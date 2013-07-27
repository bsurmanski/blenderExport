import bpy
from bpy_extras.io_utils import ExportHelper
from mathutils import *
from math import *
import struct

#normalizes all vertices, projecting them onto a sphere
def normalizeAll():
    for m in bpy.data.meshes:
        for v in m.vertices:
            sum = 0.0
            for i in range(0, 3):
                sum += v.co[i] * v.co[i]
            sum = sqrt(sum)
            for i in range(0, 3):
                v.co[i] = v.co[i] / sum

#sperically project onto plane z=1, produces x/y coords: {-1 <= x <= 1}
def planet_co_to_uv():
    sqrt2 = sqrt(2)
    sqrt3inv = 1/sqrt(3)
    for m in bpy.data.meshes:
        for v in m.vertices:
            ratio = 1 / v.co[2]
            for i in range(0, 3):
                v.co[i] = v.co[i] * (ratio)

def float_to_ushort(val):
    if val >= 1.0:
        return 2**16-1
    if val <= 0.0:
        return 0
    return int(floor(val * (2**16-1)))

def float_to_short(val):
    if val >= 1.0:
        return 2**15-1
    if val <= -1.0:
        return -(2**15)+1
    return int(round(val * (2**15-1)))

def float_to_ubyte(val):
    if val >= 1.0:
        return 2**8-1
    if val <= 0.0:
        return 0
    return int(round(val * (2**8-1)))

def vec2_to_uhvec2(val):
    return tuple((float_to_ushort(val[0]), float_to_ushort(val[1])))

def vec3_to_hvec3(val):
    return tuple((float_to_short(val[0]), float_to_short(val[1]), float_to_short(val[2])))

def is_trimesh(mesh):
    ret = True
    for face in mesh.tessfaces:
        if len(face.vertices) > 3:
            ret = False
            break
    return ret
