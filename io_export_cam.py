import bpy
from bpy_extras.io_utils import ExportHelper
from mathutils import *
from math import *
import struct
from blender_sharelib import *

"""
CAM file format export
Requirements:


HEADER:
    3 byte: magic number (CAM)
    1 byte: version number (1)
    4 byte: padding
    8

CAM:
    HEADER,
"""


def write_cam_camera(context, settings):
    buf = []
    return b''.join(buf)


# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

class CamExport(Operator, ExportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "export.cam"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export Custom Camera"

    # ExportHelper mixin class uses this
    filename_ext = ".cam"

    filter_glob = StringProperty(
            default="*.cam",
            options={'HIDDEN'},
            )

    def execute(self, context):
        f = open(self.filepath, 'wb')
        obuf = write_cam_camera(context, None)
        f.write(obuf)
        f.close()

        return {'FINISHED'}


# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(ScnExport.bl_idname, text="Custom Camera (.cam)")


def register():
    bpy.utils.register_class(CamExport)
    bpy.types.INFO_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(CamExport)
    bpy.types.INFO_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.export.cam('INVOKE_DEFAULT')