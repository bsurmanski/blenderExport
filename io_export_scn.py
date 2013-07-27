import bpy
import bpy_types
from bpy_extras.io_utils import ExportHelper
from mathutils import *
from math import *
import struct
from blender_sharelib import *
from io_export_mdl5 import *

"""
SCN file format export
Requirements:
    pack various datatypes
    specify transformations of renderable and physical objects
    specify transformations of lights
    specify transformations of cameras
    associate mesh/texture/materials (? should this not be in another contains format?)

HEADER:
    3 byte: magic number (SCN)
    1 byte: version number (1)
    2 byte: # packed resources
    2 byte: # entities
    8 byte: padding
    16 byte: name
    32

PACK:
    PACK HEADER: (PACKED TO 16 BYTES)
        1 byte: resource type (image, mesh, sound, text, etc) (MESH=1, IMAGE=2, SOUND=4, TEXT=8, CAM=10, LAMP=20)
        3 byte: resource identifier ('TGA', 'MDL', 'CAM', 'LMP', 'ARM', 'OGG', 'LUA', 'PY', etc)
        4 byte: pack data size (not inc this header; if zero, data is external (searched for by name and resource identifier))
        8 byte: padding
        16 byte: resource name
        32
    XX byte: packed data

ENT:
    ENT HEADER: (PACKED TO 16 BYTES)
        2 byte: parent id (zero indexed, if top bit is '1', no parent)
        2 byte: num resources refs
        12 byte: position (3xfloat)
        12 byte: rotation (3xfloat quaternion (normalized, implicit w))
        12 byte: scale (3xfloat)
        40
    PAKID * num resource refs
        2 byte: index into PACK array
    xx byte: Resource References (PAKID)

SCN:
    HEADER,
    PACK,
    ENT
"""

class Pak:
    def __init__(self, _type, id, obj, data):
        self.type = _type
        self.id = id
        self.obj = obj
        if hasattr(obj, 'data'):
            self.name = obj.data.name
        else:
            self.name = obj.name
        self.data = data

class PakList:
    def __init__(self, scene):
        self.pakList = []
        seen = []
        for obj in scene.objects:
            if not obj.data in seen:
                seen.append(obj.data)
                if obj.type == "MESH":
                    dat = b"" #dat = write_mdl_mesh(
                    self.add(Pak(0x01, "MDL", obj, write_mdl_mesh(obj, None)))

                    if obj.active_material:
                        textures = object_textures(obj)
                        for tex in textures:
                            self.add(Pak(0x02, "TGA", tex, b""))

                elif obj.type == "CAMERA":
                    self.add(Pak(0x10, "CAM", obj, b""))

                elif obj.type == "LAMP":
                    self.add(Pak(0x20, "LMP", obj, b""))

                else:
                    print("no know output format for \"", obj.name, "\" of type \"", obj.type, "\". Ignoring")

    def list(self):
        return self.pakList

    def length(self):
        return len(self.pakList)

    def add(self, pak):
        self.pakList.append(pak)

    def get(self, i):
        return self.pakList[i]

    def find(self, obj):
        for pak in self.pakList:
            if pak.obj == obj:
                return pak

    #assumes only meshes use more than one resource; and then only for textures
    def numResources(self, obj):
        return len(self.resourceList(obj))

    def resourceList(self, obj):
        lst = []
        lst.append(self.objID(obj))
        if self.objID(obj) == -1:
            print("ERROR: ", obj)
        if type(obj) == bpy_types.Mesh:
            if obj.active_material:
                textures = object_textures(obj)
                for tex in textures:

                    lst.append(self.objID(tex))
        return lst

    def objID(self, obj):
        cnt = 0
        for pak in self.pakList:
            if pak.obj == obj or (hasattr(obj, 'data') and hasattr(pak.obj, 'data') and pak.obj.data == obj.data):
                return cnt
            cnt+=1
        return -1



def count_object_textures(obj):
    return len(object_textures(obj))

def object_textures(obj):
    seen = []
    if obj.type == "MESH" and obj.active_material:
        for tex in obj.active_material.texture_slots:
            if tex and tex not in seen:
                seen.append(tex)
    return seen

def write_scn_header(buf, scene, pakList):
    hfmt = "3sBHH8x16s"
    header = struct.pack(hfmt,
                         b"SCN",
                         1,
                         pakList.length(), # count resources objects need (textures/meshs for mesh type)
                         len(scene.objects), # count objects in scene
                         bytes(scene.name, "UTF-8"))
    buf.append(header)

def write_scn_pack(buf, scene, type, id, name, data):
    fmt = "B3sI8x16s"
    pheader = struct.pack(fmt, type, bytes(id, "UTF-8"), len(data), bytes(name, "UTF-8"))
    buf.append(pheader)
    buf.append(data)
    pakln = len(pheader) + len(data)
    if (pakln % 16) != 0: #pack to 16 bits
        buf.append(struct.pack("x" * (16 - (pakln % 16))))

def write_scn_packs(buf, scene, pakList):
    for pak in pakList.list(): #TODO not correctly being writen in order
        write_scn_pack(buf, scene, pak.type, pak.id, pak.name, pak.data)


def write_scn_ent(buf, scene, pakList, obj, id, parent):
    fmt = "HH3f3f3f"
    eheader = struct.pack(fmt,
                          parent,
                          pakList.numResources(obj),
                          obj.location[0], obj.location[1], obj.location[2],
                          obj.rotation_quaternion[1], obj.rotation_quaternion[2], obj.rotation_quaternion[3],
                          obj.scale[0], obj.scale[1], obj.scale[2])
    buf.append(eheader)

    resref = pakList.resourceList(obj)
    for res in resref:
        buf.append(struct.pack("H", res))

    #
    #pack to 16 bits after each ent entry
    #
    entln = len(eheader) + len(resref) * 2
    if (entln % 16) != 0:
        buf.append(struct.pack("x" * (16 - (entln % 16))))

    parent = id
    for objs in obj.children:
        id += 1
        write_scn_ent(buf, scene, pakList, id, parent) #TODO parent ID
    id += 1
    return id


def write_scn_ents(buf, scene, pakList):
    objs = []
    for obj in scene.objects: # build list of roots
        if not obj.parent:
            objs.append(obj)

    cnt = 0
    for obj in objs:
        cnt = write_scn_ent(buf, scene, pakList, obj, cnt, 0xffff)


def write_scn_data(buf, scene, pakList):
    write_scn_packs(buf, scene, pakList)
    write_scn_ents(buf, scene, pakList)

def write_scn_scene(context, settings):
    buf = []
    pakList = PakList(context.scene)
    write_scn_header(buf, context.scene, pakList)
    write_scn_data(buf, context.scene, pakList)

    return b''.join(buf)


# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

class ScnExport(Operator, ExportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "export.scn"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export Custom Scene"

    # ExportHelper mixin class uses this
    filename_ext = ".scn"

    filter_glob = StringProperty(
            default="*.scn",
            options={'HIDDEN'},
            )

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
        f = open(self.filepath, 'wb')
        obuf = write_scn_scene(context, None)
        f.write(obuf)
        f.close()

        return {'FINISHED'}


# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(ScnExport.bl_idname, text="Custom Scene (.scn)")


def register():
    bpy.utils.register_class(ScnExport)
    bpy.types.INFO_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ScnExport)
    bpy.types.INFO_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.export.scn('INVOKE_DEFAULT')
