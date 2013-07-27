import bpy
from bpy_extras.io_utils import ExportHelper
from mathutils import *
from math import *
import struct
from blender_sharelib import *

"""
LMP file format export
Requirements:
    spec lamp type (point, sun, spot, hemi, area, ambient)
    spec lamp color (spec, diffuse)
    spec lamp

    Point/Spot:
        spec lamp falloff (? maybe)

HEADER:
    3 byte: magic number (LMP)
    1 byte: version number (1)
    1 byte: lamp type (0x00=ambient, 0x01=sun, 0x02=point, 0x04=spot, 0x08=hemi, 0x10=area)
    3 byte: diffuse color (RGB)
    8

LMP:
    HEADER,
    PACK,
    ENT
"""


def write_lmp_lamp(context, settings):
    buf = []
    return b''.join(buf)


# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

class LmpExport(Operator, ExportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "export.lmp"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export Custom Lamp"

    # ExportHelper mixin class uses this
    filename_ext = ".lmp"

    filter_glob = StringProperty(
            default="*.lmp",
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
        obuf = write_lmp_lamp(context, None)
        f.write(obuf)
        f.close()

        return {'FINISHED'}


# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(ScnExport.bl_idname, text="Custom Lamp (.lmp)")


def register():
    bpy.utils.register_class(LmpExport)
    bpy.types.INFO_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(LmpExport)
    bpy.types.INFO_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.export.lmp('INVOKE_DEFAULT')
