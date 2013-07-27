import bpy
from bpy_extras.io_utils import ExportHelper
from mathutils import *
from math import *
import struct

"""
mesh pose library export

HEADER:
    3 byte: magic number 'POS'
    1 byte: version number (1)
    1 byte: number of bones
    1 byte: number of poses/frames
    16 byte: pose name (including NULL byte)
    10 byte: padding
    32                          TODO: pose indexing (for multi-libraries)

BONE_POSE:
    16 byte: quaternion rotation (4 * 4 byte float(x,y,z,w)) (centered at head, delta from default pos)
    12 byte: offset (3 * 4 byte float (x,y,z))
    4 byte: scale factor (4 byte float)
    32

BONE_HEADER:
    12 byte head position (3 * 4 byte float)
    12 byte tail position (3 * 4 byte float)
    1  byte ID
    1  byte parent ID
    1  byte nchildren
    5  byte padding
    32

POS:
    HEADER
    BONEs
    BONE_POSEs (in order by ID, packed all of a bone's frames sequentially)

"""

def find_bone_parentid(bones, bone):
    for pbone in enumerate(bones):
        if pbone[1] == bone[1].parent:
            return pbone[0]
    return 255

#blist format: (boneid, parentid, bone, group)
def get_bone_list(obj):
    blist = []
    arm = obj.find_armature()
    for bone in enumerate(arm.data.bones):
        b_group = None
        for group in arm.pose_library.groups:
            if group.name == bone[1].name:
                b_group = group
                break
        p_id = find_bone_parentid(arm.data.bones, bone)
        assert(p_id == 255 or p_id < bone[0]) # parent id must be less than id
        blist.append((bone[0], p_id, bone[1], b_group))
    return blist

"""
HEADER:
    3 byte: magic number 'POS'
    1 byte: version number (1)
    1 byte: number of bones
    1 byte: number of poses/frames
    16 byte: pose name
    10 byte: padding            TODO: pose name?
    32                          TODO: pose indexing (for multi-libraries)
"""
def write_pos_header(f, obj, blist):
    hfmt = "3sBBB15s" + 'x' * 11
    framerange = obj.find_armature().pose_library.frame_range
    header = struct.pack(hfmt, b"POS", 1,
                len(blist), #number of bones
                int(framerange[1] - framerange[0] + 1), #number of poses
                bytes(obj.find_armature().pose_library.name, "UTF-8"))
    f.write(header)

"""
BONE:
    12 byte head position (3 * 4 byte float)
    12 byte tail position (3 * 4 byte float)
    1  byte ID
    1  byte parent ID
    1  byte nchildren
    5  byte padding
    32
"""
def write_pos_bones(file, obj, blist):
  tmat = Matrix.Rotation(-pi/2.0, 3, Vector((1,0,0))).to_4x4() #turns verts right side up (+y)
  bfmt = "ffffffBBBxxxxx"
  if(blist and len(blist) > 0):
    for b in blist:
      BONEID = 0; BONEPID = 1; BONEBONE = 2
      bone = b[BONEBONE]
      offset = Vector(obj.find_armature().location - obj.location) / 2
      amat = obj.find_armature().matrix_local.to_3x3().to_4x4()
      head = tmat * amat * (Vector(bone.head_local) + offset)
      tail = tmat * amat * (Vector(bone.tail_local) + offset) #TODO: no local
      
      print(head)
      bbits = struct.pack(bfmt,
                    head[0], head[1], head[2],
                    tail[0], tail[1], tail[2],
                    b[BONEID], #ID
                    b[BONEPID], # parent ID
                    len(bone.children)) # nchildren
      file.write(bbits)


def set_channel(framen, channel, pos, rot, scale):
    if channel.data_path.endswith("location"):
        pos[channel.array_index] = channel.evaluate(framen)
    elif channel.data_path.endswith("rotation_quaternion"):
        rot[channel.array_index] = channel.evaluate(framen)
    elif channel.data_path.endswith("scale"):
        scale[channel.array_index] = channel.evaluate(framen)
    else:
        raise Exception("Unknown FCurve channel data path")

def get_bone_pose(bone, framen):
    GROUP = 3; BONE = 2
    pos = Vector((0,0,0,0))
    rot = Quaternion((1,0,0,0))
    scale = Vector((1,1,1,1))
    for channel in bone[GROUP].channels:
        set_channel(framen, channel, pos, rot, scale)

    bquat = bone[BONE].matrix_local.to_quaternion()
    bmat = bone[BONE].matrix_local

    pos = bmat * pos;
    rot = (bmat.inverted() * rot.to_matrix().to_4x4() * bmat).to_quaternion().normalized()
    return (pos, rot, scale)

"""
BONE_POSE:
    16 byte: quaternion rotation (4 * 4 byte float(x,y,z,w)) (centered at head, delta from default pos)
    12 byte: offset (3 * 4 byte float (x,y,z))
    4 byte: scale factor (4 byte float)
    32
"""
def write_pos_poses(f, obj, blist, settings):
    pfmt = "ffffffff"
    POS=0;ROT=1;SCL=2
    POSE_N = 2; POSE_IN_TUPLE = 1
    framerange = obj.find_armature().pose_library.frame_range
    
    for bone in blist:
        for i in range(int(framerange[0]), int(framerange[1])+1):        
            pose = get_bone_pose(bone, i)
            print(pose[ROT])
            pbits = struct.pack(pfmt,
            pose[ROT].x, -pose[ROT].z, pose[ROT].y, pose[ROT].w,    #convert WXYZ -> XZYW
            pose[POS].x, pose[POS].z, pose[POS].w, pose[SCL].length / 2.0) #sorry, linear scale only :(
            f.write(pbits)

def write_pos_pose(context, filepath, settings):
    if not context.object.type == "MESH":
            raise Exception("Mesh must be selected, " + context.object.type + " was given")

    obj = context.object
    mesh = obj.data

    if not obj.find_armature().type == "ARMATURE":
        raise Exception("Mesh must have a parent Armature applied to it");
    arm = obj.find_armature()

    blist = get_bone_list(obj)

    f = open(filepath, 'wb')
    write_pos_header(f, obj, blist)
    write_pos_bones(f, obj, blist)
    write_pos_poses(f, obj, blist, settings)
    f.close()
    return {'FINISHED'}

# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

class PosExport(Operator, ExportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "export.pos"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export Custom Pose"

    # ExportHelper mixin class uses this
    filename_ext = ".pos"

    filter_glob = StringProperty(
            default="*.pos",
            options={'HIDDEN'},
            )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    poses = []
    obj = bpy.context.object
    if obj.type == "MESH":
        arm = obj.find_armature()
        if arm and arm.type == "ARMATURE":
            assert(arm.pose_library and "please set pose_library in sidepane");
            for pos in arm.pose_library.pose_markers:
                poses.append((pos.name, pos.name, "_"))

    use_setting = BoolProperty(
           name="Append Pose Name",
            description="Append the name of the pose to the filename",
            default=True,
            )

    #type = EnumProperty (
    #        name="Pose",
    #        description="Choose Pose to Export",
    #        items=tuple(poses),
    #        default=poses[0][0],
    #        )


    def execute(self, context):
        #TODO: use setting
        return write_pos_pose(context, self.filepath, type)


# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    #raise Exception(use_setting)
    self.layout.operator(PosExport.bl_idname, text="Custom Pose (.pos)")


def register():
    bpy.utils.register_class(PosExport)
    bpy.types.INFO_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(PosExport)
    bpy.types.INFO_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.export.pos('INVOKE_DEFAULT')