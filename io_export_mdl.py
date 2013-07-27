import bpy
from mathutils import *
from math import *
import struct

def write_mdl_data(context, filepath):
        print("Calculating Model Data...")
        
        objects = bpy.data.objects
        faces = 0
        num_verts = 0
        
        for obj in objects:
                if obj.type == "MESH": #for all meshes
                        faces += len(obj.data.faces)
                        num_verts += len(obj.data.vertices)
                        
        num_actions = len(bpy.data.actions) #get num actions
        
        f = open(filepath, 'w')
        f.write("MODL")
        f.write("{0:4d} {1:6d} {2:6d}".format(num_actions, faces, num_verts)+"{0:c}".format(0)*4) # file header
        write_face_vert_relations (objects, f)    
        write_action_data(objects, f)
        write_static_meshes(objects,f)
        f.close()

        return {'FINISHED'}
    
def write_action_data(objects, f):
    for actions in bpy.data.actions: # for all actions 
        num_frames = int(actions.frame_range[1] - actions.frame_range[0]) #get num frames for action
        f.write("ACTN " + actions.name + "{0:4d}".format(num_frames) + "{0:c}".format(0)*4) #write action header
        for frame in range (int(actions.frame_range[0]), int(actions.frame_range[1])):
            write_frame_data (objects, actions, frame, f) #write each frame of the action

def write_static_meshes(objects, f):
    f.write("MESH ")
    for obj in objects:
        if obj.type == "MESH" and not obj.parent:
            obj_matrix = obj.rotation_euler.to_matrix()*obj.scale[0]
            for verts in obj.data.vertices:
                write_vertex((verts.co + obj.location)*obj_matrix, f)

def write_face_vert_relations (objects, f):
        f.write("FACE ") # face index
        faceSum = 0
        for obj in objects:
                if obj.type == "MESH": #for all meshes
                    for faces in obj.data.faces:
                        for indices in faces.vertices:
                                #f.write("{0:2c}".format(indices+faceSum))
                                f.write(str(indices+faceSum))
                                f.write(" ")
                        f.write(chr(0)*2) #write 2 null bytes
                    faceSum += len (obj.data.faces) # for multiple meshes, offset faces
    

def write_frame_data(objects, action, frame, f):
        f.write("FRME ") #write magic number
        for obj in objects:
                if obj.type == "MESH": #for all meshes
                    object_matrix = Matrix()#obj.matrix_local # MODIFY SO GETS OBJECT MOVEMENT, NOT JUST STATIC MATRIX
                    if obj.parent and obj.parent.type == "ARMATURE":
                     arm = obj.find_armature() #find armature
                     arm_matrix = get_armature_matrix(arm) # BUGGY!!!
                     bone_matrices = dict()
                     for bones in arm.data.bones: 
                                boneParent = None
                                if bones.parent:
                                        boneParent = bones.parent.name
                                bone_matrices[bones.name] = get_bone_matrix(action, frame, arm, bones.name, bone_matrices.get(boneParent))
                     
                     vertexGroups = list()
                     for groups in obj.vertex_groups: #get vertex groups in obj
                                vertexGroups.append(groups.name)
                                                            
                     for verts in obj.data.vertices:
                            totWeight = 0
                            modifiedVert = Vector()
                            for groups in verts.groups:
                                totWeight += groups.weight
                                modifiedVert += groups.weight*verts.co*object_matrix*bone_matrices[vertexGroups[groups.group]]#*arm_matrix
                            modifiedVert /= totWeight
                            write_vertex(modifiedVert, f)     
                             
                                
def write_vertex(vertex, f):
        for i in range(0,3):
             f.write(str(vertex[i]))
             f.write(" ")
        f.write(chr(0))


def get_armature_matrix(armature):
    return armature.matrix_basis

def get_bone_matrix(action, frame, armature, bone, parent_bone_matrix):
        
        if not parent_bone_matrix: #HACK TO GET ROTATION RIGHT!!
                parent_bone_matrix = Matrix(((0,1,0,0),(-1,0,0,0),(0,0,1,0),(0,0,0,1)))#armature.rotation_euler.to_matrix().to_4x4()*Matrix(((0,1,0,0),(-1,0,0,0),(0,0,1,0),(0,0,0,1)))#.identity()#armature.matrix_world
        
        #if not frame:
        #    print (action, frame)
        #    return Matrix()
        
        if not bone or not armature or not action:
                return Matrix()*parent_bone_matrix
                
        fcurves = action.fcurves
        if not fcurves:
                return Matrix().identity()*parent_bone_matrix
        scale = eval_fcurves(fcurves, bone, "scale", frame)
        location = eval_fcurves(fcurves, bone, "location", frame)
        rotation = eval_fcurves(fcurves,bone, "rotation_quaternion", frame)
        return rotation*parent_bone_matrix*location*scale


def eval_fcurves (fcurves, bone, action, frame):
        data = list()
        for curves in fcurves:
                if bone in curves.data_path.split("\"") and action in curves.data_path.split("."):
                        data.append(curves.evaluate(frame))
        if not data:
                return Matrix() #no valid curve found, return identity matrix
            
        dataMat = Matrix()
        if action == "scale":
                return Matrix(((data[0],0,0,0),(0,data[1],0,0),(0,0,data[2],0),(0,0,0,1)))
        elif action == "location":
                return Matrix(((1,0,0,data[0]),(0,1,0,data[1]),(0,0,1,data[2]),(0,0,0,1)))
        elif action == "rotation_quaternion":
                return Quaternion(data).to_matrix().to_4x4()
        else:
                return Matrix() #not valid action name
                        
                            
# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from io_utils import ExportHelper

from bpy.props import *


class ExportMdlFile(bpy.types.Operator, ExportHelper):
        '''Exports a custom model file created by Brandon Surmanski'''
        bl_idname = "export.mdl" # this is important since its how bpy.ops.export.mdl_file is constructed
        bl_label = "Export mdl File"
        
        # ExportHelper mixin class uses this
        filename_ext = ".mdl"

        filter_glob = StringProperty(default="*.mdl", options={'HIDDEN'})

     #List of operator properties, the attributes will be assigned
     #to the class instance from the operator settings before calling.
     #use_setting = BoolProperty(name="Example Boolean", description="Example Tooltip", default= True)

     # type = bpy.props.EnumProperty(items=(('OPT_A', "First Option", "Description one"), ('OPT_B', "Second Option", "Description two.")),
     #                                      name="Example Enum",
     #                                   description="Choose between two items",
     #                                  default='OPT_A')

        @classmethod
        def poll(cls, context):
                #return context.active_object != None
                return True #bpy.data.len > 0

        def execute(self, context):
                return write_mdl_data(context, self.filepath)


# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
        self.layout.operator(ExportMdlFile.bl_idname, text="Brandon Surmanski Custom Model (.mdl)")

bpy.types.INFO_MT_file_export.append(menu_func_export)

def register():
    bpy.utils.register_class(ExportMdlFile)
    bpy.types.INFO_MT_file_export.append(menu_func_export)
    

if __name__ == "__main__":
        register()
        bpy.ops.export.mdl('INVOKE_DEFAULT')