import bpy
from bpy_extras.io_utils import ExportHelper
from mathutils import *
from math import *
import struct

"""
mesh pose export

HEADER:
3 byte: magic number 'POS'
1 byte: version number (1)
1 byte: number of bones
16 byte: pose name
11 byte: padding            TODO: pose name?
32

BONE_POSE:
    16 byte: quaternion rotation (4 * 4 byte float(x,y,z,w)) (centered at head, delta from default pos)
    12 byte: offset (3 * 4 byte float (x,y,z))
    4 byte: scale factor (4 byte float)
    32
    
POS:
    HEADER
    BONE_POSEs (in order by ID)
      
"""
"""
def set_channel(obj, framen, channel, pos, rot, scale):
    if channel.data_path.endswith("location"):
        pos[channel.array_index] = channel.evaluate(framen)
    elif channel.data_path.endswith("rotation_quaternion"):
        rot[channel.array_index] = channel.evaluate(framen)
    elif channel.data_path.endswith("scale"):
        scale[channel.array_index] = channel.evaluate(framen)
    else:
        raise Exception("Unknown FCurve channel data path")

def get_bone_pose(obj, framen, group):
    arm = obj.find_armature()
    pos = Vector((0,0,0,0))
    rot = Vector((0,0,0,1))
    scale = Vector((1,1,1,1))
    for channel in group.channels:
        set_channel(obj, framen, channel, pos, rot, scale)
    rot.normalize()
    return (pos, rot, scale)
"""

def find_bone_parentid(bones, bone):
    for pbone in enumerate(bones):
        if pbone[1] == bone.parent
            return pbone[0]

def get_bone_list(obj)
    blist = []
    arm = obj.find_armature()
    for bone in enumerate(arm.data.bones):
        b_group = None
        for group in arm.pose_library.groups:
            if group.name == bone.name:
                b_group = group
                break
        p_id = find_bone_parentid(arm.data.bones, bone)
        assert(p_id != None && p_id < bone[0]) # parent id must be less than id
        blist.append((bone[0], bone[1], b_group))
    return blist 

"""
def get_pose(obj, framen):
    pose = []
    for group in obj.find_armature().pose_library.groups:
        print(group.name)
        pose.append(get_bone_pose(obj, framen, group))
    return pose

def get_pose_list(obj):
    arm = obj.find_armature()
    plist = []
    for marker in arm.pose_library.pose_markers:
        plist.append((marker.name, get_pose(obj, marker.frame)))
    return plist
"""

def write_pos_header(f, obj, plist):
    hfmt = "3sBB" + 'x' * 27
    
    header = struct.pack(hfmt, b"POS", 1,
                len(obj.find_armature().pose_library.groups)) #number of bones
    f.write(header)

def write_pos_poses(f, obj, plist, settings):
    pfmt = "ffffffff"
    POS=0;ROT=1;SCL=2
    POSE_N = 2; POSE_IN_TUPLE = 1
    for bone in plist[POSE_N][POSE_IN_TUPLE]:
        pbits = struct.pack(pfmt, 
        bone[ROT][1], bone[ROT][2], bone[ROT][3], bone[ROT][0],    #convert WXYZ -> XZYW
        bone[POS][0], bone[POS][2], bone[POS][1], bone[SCL].length / 2.0) #sorry, linear scale only :(
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
    plist = get_pose_list(obj)

    f = open(filepath, 'wb')
    write_pos_header(f, obj, plist)
    write_pos_poses(f, obj, plist, settings)
    #write_mdl_bones(f, obj)
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
            for pos in arm.pose_library.pose_markers:
                poses.append((pos.name, pos.name, "_"))
    
    use_setting = BoolProperty(
           name="Append Pose Name",
            description="Append the name of the pose to the filename",
            default=True,
            )

    type = EnumProperty (
            name="Pose",
            description="Choose Pose to Export",
            items=tuple(poses),
            default=poses[0][0],
            )
    

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