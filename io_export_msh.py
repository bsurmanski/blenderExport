bl_info = {
    "name":         "MSH File Format",
    "author":       "Brandon Surmanski",
    "blender":      (2,7,3),
    "version":      (0,0,2),
    "location":     "File > Import-Export",
    "description":  "Export custom MSH format",
    "category":     "Import-Export"
}

import bpy
import bmesh
from bpy_extras.io_utils import ExportHelper
from mathutils import *
from math import *
import struct
import bisect

"""
MSH file format export

HEADER:
    3 byte: magic number (MDL)
    1 byte: version number (5)
    4 byte: number of verts
    4 byte: number of faces
    4 byte: number of edges
    1 byte: number of bones
    15 byte: name
    32

VERT:
    12 byte: position (3 * 4 byte float)
    6 byte: normal (3 * 2 byte signed short) (normalized from -32768 to 32767) #TODO implicit Z
    4 byte: uv coordinate (2 * 2 byte) (normalized from 0 to 65535)
    3 byte: RGB vertex color
    1 byte: material index
    1 byte: boneID 1
    1 byte: boneID 2
    1 byte: bone weight 1
    1 byte: bone weight 2
    2 byte: incident edge id
    32

FACE:
    6 byte: vertex indices
    6

EDGE:
    2 byte: vertexids
    2 byte: faceids
    2 byte: edgeids left and right of vertex[0]
    2 byte: edgeids left and right of vertex[1]
    8

MSH:
    HEADER,
    VERTS,
    FACES,
    EDGES
"""

slicesUvs = True

#
# SHARELIB
#

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

#
#
#

def bone_weight_normalize(bones):
    BONEW1 = 2; BONEW2 = 3
    b_sum = bones[BONEW1] + bones[BONEW2]
    if b_sum > 0:
        bones[BONEW1] = float_to_ubyte(bones[BONEW1] / b_sum)
        bones[BONEW2] = float_to_ubyte(bones[BONEW2] / b_sum)
    else:
        bones[BONEW1] = 0
        bones[BONEW2] = 0
    return bones

def bone_id_of_group(obj, groupid, blist):
    BONE = 3
    nm = obj.vertex_groups[groupid].name
    for i in range(0, len(blist)):
        if(nm == blist[i][BONE].name):
            print(nm + " is group " + str(i));
            return i
    return None

def vert_get_bones(obj, vert, blist):
    boneid = [255, 255]
    bonew = [0.0, 0.0]
    for group in vert.groups:
        g_boneid = bone_id_of_group(obj, group.group, blist)
        if g_boneid != None:
            if group.weight > bonew[0]:
                bonew[1] = bonew[0]
                boneid[1] = boneid[0]
                bonew[0] = group.weight
                boneid[0] = g_boneid
            elif group.weight > bonew[1]:
                bonew[1] = group.weight
                boneid[1] = g_boneid
    return bone_weight_normalize([boneid[0], boneid[1], bonew[0], bonew[1]])

def find_bone_parentid(arm, bone):
    if(bone.parent):
        for i in range(len(arm.data.bones)):
            if(arm.data.bones[i] == bone.parent):
                return i
    return 255

def get_bone_list(obj):
    armature = obj.find_armature()
    blist = []
    if(armature):
        for i in range(0, len(armature.data.bones)):
            bone = armature.data.bones[i]
            pid = find_bone_parentid(armature, bone)
            blist.append([bone.name, i, pid, bone])
    return blist

####

class Vert(object):
    def __init__(self, bmv):
        self.bmv = bmv

    def __getattr__(self, name):
        return getattr(self.bmv, name)

class Face(object):
    def __init__(self, bmf):
        self.bmf = bmf

    def __getattr__(self, name):
        return getattr(self.bmf, name)

    def getUv(self, layer, i):
        luv = self.bmf.loops[i][layer].uv
        return Uv(luv.x, luv.y, self.bmf.loops[i].vert.index, None) # kinda weird, i'm not adding color to this UV

# vert_index, 0 or 1. first or second vert in edge
def get_edge_prevwing(bmedge, vert_index):
    loop = bmedge.link_loops[1] # its either one or the other
    if bmedge.verts[vert_index].index == bmedge.link_loops[0].vert.index:
        loop = bmedge.link_loops[0]
    return loop.link_loop_prev.edge

def get_edge_nextwing(bmedge, vert_index):
    loop = bmedge.link_loops[1] # its either one or the other
    if bmedge.verts[vert_index].index == bmedge.link_loops[0].vert.index:
        loop = bmedge.link_loops[0]
    return loop.link_loop_next.edge

def get_edge_vertid(bmedge, vert_index):
    return bmedge.verts[vert_index].index

def get_edge_faceid(bmedge, face_index):
    # TODO: check if this is ordered consistantly
    # I suspect bmesh makes no guarentee that faces[0] is left-wise (as i would expect)
    return bmedge.link_faces[face_index].index 

class Edge(object):
    def __init__(self, bme):
        self.bme = bme

    def __getattr__(self, name):
        return getattr(self.bme, name)

class Uv(object):
    def __init__(self, uvx, uvy, vindex, color, material=0):
        self.uvx = float_to_ushort(uvx)
        self.uvy = float_to_ushort(uvy)
        self.vindex = vindex
        self.color = color
        self.material = material

    def __eq__(self, other):
        return self.uvx == other.uvx and self.uvy == other.uvy and self.vindex == other.vindex

    def __hash__(self):
        return self.vindex << 32 | self.uvx << 16 | self.uvy

    def __repr__(self):
        return "(Uv " + str(self.uvx) + ", " + str(self.uvy) + ", " + str(self.vindex) + ", " + str(self.color) + ")"


class Mesh(object):
    def __init__(self, mesh, settings):
        mesh.update(calc_tessface=True)

        self.bm = bmesh.new()
        self.bm.from_mesh(mesh)
        bmesh.ops.triangulate(self.bm, faces=self.bm.faces)

        self.mesh = mesh
        self.settings = settings
        self.verts = []
        self.faces = []
        self.edges = []
        self.uvs = dict()

        self.uv_layer = self.bm.loops.layers.uv.verify()
        self.color_layer = self.bm.loops.layers.color.verify()

        for v in self.bm.verts:
            self.verts.append(Vert(v))

        for f in self.bm.faces:
            self.faces.append(Face(f))

            # make set of uvs for each face
            for l in f.loops:
                luvx = 0
                luvy = 0
                if settings['sliceUvs']: # if we dont add this, uvs are unique on vertid
                    luvx = l[self.uv_layer].uv.x
                    luvy = l[self.uv_layer].uv.y
                color = l[self.color_layer]
                iuv = Uv(luvx, luvy, l.vert.index, color, f.material_index)
                if iuv not in self.uvs:
                    self.uvs[iuv] = len(self.uvs) # add uv to set, value is uv index

        for e in self.bm.edges:
            self.edges.append(Edge(e))

    def __getattr__(self, name):
        return getattr(self.bm, name)

    def uv_layer(self):
        return self.bm.loops.layers.uv.verify()

    def nverts(self):
        return len(self.uvs)

    def nfaces(self):
        return len(self.faces)

    def nedges(self):
        if not self.settings['sliceUvs']:
            return len(self.edges)
        return 0

    def serialize(self):
        buf = []
        buf.append(self.serialize_header())
        buf.append(self.serialize_verts())
        buf.append(self.serialize_faces())
        if not self.settings['sliceUvs']:
            buf.append(self.serialize_edges())
        return b''.join(buf)

    def serialize_header(self):
        hfmt = "3sBIIIB15s"
        hpack = struct.pack(hfmt, b"MDL", 5,
                    self.nverts(),
                    self.nfaces(),
                    self.nedges(),
                    0,               # number of bones
                    bytes(self.mesh.name, "UTF-8"))
        assert(len(hpack) == 32)
        return hpack

    def serialize_uv(self, uv):
        v = self.bm.verts[uv.vindex]
        rows = [[1, 0, 0, 0],
                [0, 0, 1, 0],
                [0,-1, 0, 0],
                [0, 0, 0, 1]]
        tmat = Matrix(rows)
        co = tmat * v.co
        normal = tmat * v.normal
        vpack = struct.pack("fffhhhHHBBBBBBBBH",
                        co.x,
                        co.y,
                        co.z,
                        float_to_short(normal.x),
                        float_to_short(normal.y),
                        float_to_short(normal.z),
                        uv.uvx, uv.uvy, # uvs
                        float_to_ubyte(uv.color.r), 
                        float_to_ubyte(uv.color.g),
                        float_to_ubyte(uv.color.b), 
                        0, # material id
                        0, 0, # bone ids
                        0, 0, # bone weights
                        v.link_edges[0].index)
        assert(len(vpack) == 32)
        return vpack

    def serialize_verts(self):
        buf = []
        for uv in sorted(self.uvs, key=self.uvs.get): # should be incremental
            buf.append(self.serialize_uv(uv))
        return b''.join(buf)

    def serialize_face(self, f):
        buf = []

        # if there are no UVs, the a UV just represents a vert
        for i in range(0, 3):
            uv = f.getUv(self.uv_layer, i)
            # if we shouldn't slice uvs, dont use uv's provided by face
            if not self.settings['sliceUvs']:
                uv.uvx = 0 
                uv.uvy = 0
            buf.append(struct.pack("H", self.uvs[uv]))
        # buf.append(struct.pack("H", f.edges[0].index)) # cannot add edge reference because it breaks OpenGL
        fpack = b''.join(buf)
        assert(len(fpack) == 6)
        return fpack

    def serialize_faces(self):
        buf = []
        for f in self.faces:
            buf.append(self.serialize_face(f))
        return b''.join(buf)

    # only valid if not using UVs
    def serialize_edge(self, e):
        epack = struct.pack("HHHHHHHH",
                            get_edge_vertid(e, 0),
                            get_edge_vertid(e, 1),
                            get_edge_faceid(e, 0),
                            get_edge_faceid(e, 1),
                            get_edge_prevwing(e, 0).index,
                            get_edge_nextwing(e, 0).index,
                            get_edge_prevwing(e, 1).index,
                            get_edge_nextwing(e, 1).index)
        assert(len(epack) == 16)
        return epack

    def serialize_edges(self):
        buf = []
        for e in self.edges:
            buf.append(self.serialize_edge(e))
        return b''.join(buf)
            

import logging
def serialize_mesh(obj, settings):
    buf = []
    bpy.ops.object.mode_set(mode='OBJECT')
    print('serialize mesh...')
    mesh = Mesh(obj.data, settings)
    return mesh.serialize()


# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

class MdlExport(Operator, ExportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "export.mdl"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export Custom Model"

    # ExportHelper mixin class uses this
    filename_ext = ".msh"

    filter_glob = StringProperty(
            default="*.msh",
            options={'HIDDEN'})

    sliceUvs = BoolProperty(
            name="Slice UV mapping",
            description="If true, vertices will be split so there "
                        "is one vertex entry per unique UV", 
            default=True,)

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    """
    use_setting = BoolProperty(
           name="Example Boolean",
            description="Example Tooltip",
            default=True,
            )

    type = EnumProperty(
            name="Example Enum",
            description="Choose between two items",
            items=(('OPT_A', "First Option", "Description one"),
                   ('OPT_B', "Second Option", "Description two")),
            default='OPT_A',
            )
    """

    def execute(self, context):
        if not context.object.type == "MESH":
            raise Exception("Mesh must be selected, " + context.object.type + " was given")

        obj = context.object

        f = open(self.filepath, 'wb')
        obuf = serialize_mesh(obj, {'sliceUvs': self.sliceUvs})
        f.write(obuf)
        f.close()
        return {'FINISHED'}


# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(MdlExport.bl_idname, text="Custom Model (.msh)")


def register():
    #bpy.utils.register_class(MdlExport)
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(MdlExport)
    bpy.types.INFO_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

    # test call
    #bpy.ops.export.mdl('INVOKE_DEFAULT')
