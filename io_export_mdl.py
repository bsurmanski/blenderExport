import bpy
from bpy_extras.io_utils import ExportHelper
from mathutils import *
from math import *
import struct

bl_info={
        "name": "Brandon Surmanski MDL Format",
        "author": "Brandon Surmanski",
        "blender": (2,5,8),
        "api": 35622,
        "location": "File > Export",
        "description":("Export MDL mesh"),
        "warning":"",
        "wiki_url":"",
        "tracker_url":"",
        "support": 'NONE',
        "category": "Export"
        }
        
MDL_FMT = 2

"""
HEADER:
    3 byte: magic number (MDL)
    1 byte: version number (2)
    4 byte: number of verts
    4 byte: number of edges
    4 byte: number of faces
    4 byte: number of unique texture vertices (UVs)
    1 byte: format
    11 byte: padding
    
VERT:
    2 byte: incident edge (index)
    2 byte: incident face (index)
    12 byte: position (3 * 4 byte float)
    
EDGE:
    4 byte: verts (2 * 2 byte index)
    4 byte: faces (2 * 2 byte index)
    8 byte: winged edges [4 * 2 byte index](aprev, anext, bprev, bnext)
    
FACE:
    2 byte: incident edge (index)
    6 byte: uv indices
    6 byte: normal (3 * (2 byte) coordinate (each component normalized for -32768 to 32767)
    2 byte: padding
                    
UV:
    2 byte: vertice index
    4 byte: uv coordinate (2 * 2 byte) (normalized from 0 to 65535)
    2 byte: padding
    
    
MDL:
    HEADER,
    VERTS,
    EDGES,
    FACES
"""

def extend(lst, sz):
    for i in range(0, sz):
        lst += [None]
        
def float_to_ushort(val):
    if val >= 0.999999999:
        return 2**16-1
    if val <= 0.0:
        return 0
    return int(floor(val * (2**16-1)))

def twos_cmpl(val):
    if val < 0:
        return 2**16 + val
    return val

def float_to_short(val):
    if val >= 0.99999999:
        return 2**15-1
    if val <= -0.99999999:
        return twos_cmpl(-2**15)
    return twos_cmpl(int(round(val * 2**15)))

class Edge():
    def __init__(self, mdl, edge):
        self.mdl = mdl
        self.edge = edge
        verts_tmp = mdl.mesh.edges[edge.index].vertices
        self.verts = [mdl.mesh.vertices[verts_tmp[0]], mdl.mesh.vertices[verts_tmp[1]]]
        self.faces = [None, None]
        self.awing = [None, None]
        self.bwing = [None, None]

    def add_face(self, face):
        ekeys = face.edge_keys
        found = 0
        for i in range(0, len(ekeys)):

            if self.verts[0].index in ekeys[i] and self.verts[1].index in ekeys[i]:

                found += 1

                if self.verts[0].index in ekeys[i-1]: #left face
                    self.faces[0] = face
                    self.awing[0] = self.mdl.edgeDict[ekeys[i-1]]
                    self.bwing[1] = self.mdl.edgeDict[ekeys[(i+1)%len(ekeys)]]

                elif self.verts[1].index in ekeys[i-1]: #right face
                    self.faces[1] = face
                    self.awing[1] = self.mdl.edgeDict[ekeys[(i+1)%len(ekeys)]]
                    self.bwing[0] = self.mdl.edgeDict[ekeys[i-1]]

                else:
                    raise Exception("Face is neither the left or right of the edge")

        if found != 1:
            raise Exception("Could not find adjacent faces")
            
    # done at the end, if one of the wings is None, that means the mesh is not
    # a closed boundary surface. Fix this problem by wrapping the face around the 
    # corner
    def fix_wings(self):
        if self.awing[0] == None:
            self.awing[0] = self.edge.index
        if self.awing[1] == None:
            self.awing[1] = self.edge.index
            
        if self.bwing[0] == None:
            self.bwing[0] = self.edge.index
        if self.bwing[1] == None:
            self.bwing[1] = self.edge.index
            


class Vert():
    def __init__(self, mdl, vert):
        self.mdl = mdl
        self.incidentEdge = None
        self.vert = vert

    def add_edge(self, edge):
        self.incidentEdge = edge

class Face():
    def __init__(self, mdl, face):
        self.mdl = mdl
        self.incidentEdge = None
        self.face = face
        tnorm = mdl.tmat * face.normal
        self.normal = [float_to_short(normi) for normi in tnorm]
        
        if mdl.mesh.uv_textures.active != None:
            self.uvs = [tuple(mdl.mesh.uv_textures.active.data[face.index].uv[i]) for i in range(0,3)]
            self.uvs = list([mdl.addUV(face.vertices[i], self.uvs[i]) for i in range(0,3)]) 
        else:
            self.uvs = list([0] * 3)
            
    def add_edge(self, edge):
        self.incidentEdge = edge
       

class MDL(bpy.types.Operator, ExportHelper):
    '''Exports a custom model file create by Brandon Surmanski'''
    bl_idname = "export.mdl2"
    bl_label = "Export MDL2 File"
    filename_ext = ".mdl"

    def __init__(self):
        if not bpy.context.object.type == "MESH":
            raise Exception("Mesh must be selected, " + bpy.context.object.type + " was given")
            
        self.tmat = Matrix.Rotation(-pi/2.0, 3, Vector((1,0,0)))

        self.mesh = bpy.context.object.data
        self.verts = []
        self.faces = []
        self.edges = []
        self.uvlist = list()
        self.ntexco = 0

        self.edgeDict = dict()
        for edge in self.mesh.edges:
            self.edgeDict[edge.key] = edge.index

        extend(self.edges, len(self.edgeDict))

        # create edge relations dependant on faces
        for face in self.mesh.faces:
            self.faces.append(Face(self, face))
            for edge_key in face.edge_keys:
                i = self.edgeDict[edge_key]
                if self.edges[i] is None:
                    self.edges[i] = Edge(self, self.mesh.edges[i])
                self.edges[i].add_face(face)

        self.verts.extend([Vert(self, vert) for vert in self.mesh.vertices])
        
        for edge in self.edges:
            vindex = edge.verts[0].index
            self.verts[vindex].add_edge(edge)

            vindex = edge.verts[1].index
            self.verts[vindex].add_edge(edge)

            if edge.faces[0] == None:
                edge.faces[0] = edge.faces[1]
            findex = edge.faces[0].index
            self.faces[findex].add_edge(edge)

            if edge.faces[1] == None:
                edge.faces[1] = edge.faces[0]
            findex = edge.faces[1].index
            self.faces[findex].add_edge(edge)

        self.format = MDL_FMT
        self.ofile = 0
        

    def addUV(self, v_id, uv):
        entry = tuple((v_id, float_to_ushort(uv[0]), float_to_ushort(uv[1])))
        if(entry not in self.uvlist):
            self.uvlist.append(entry)
        return self.uvlist.index(entry)

    def write_header(self):
        hfmt = "3sBIIII" + 'x' * 12
        header = struct.pack(hfmt, b"MDL", 2,
                    len(self.verts), len(self.edges), len(self.faces), len(self.uvlist))
        self.ofile.write(header)

    def write_verts(self):
        vfmt = "HHfff"
        for vert in self.verts:
            co = self.tmat * vert.vert.co 
            vbits = struct.pack(vfmt, vert.incidentEdge.edge.index,
                                vert.incidentEdge.faces[0].index,
                                co[0], co[1], co[2])
            self.ofile.write(vbits)            

    def write_edges(self):
        efmt = "HHHHHHHH"
        for edge in self.edges:
            edge.fix_wings()
            ebits = struct.pack(efmt, edge.verts[0].index, edge.verts[1].index,
                    edge.faces[0].index, edge.faces[1].index, 
                    edge.awing[0], edge.awing[1], edge.bwing[0], edge.bwing[1])
            self.ofile.write(ebits)

    def write_faces(self):
        ffmt = "H" + "H" * 3 + "H" * 3 + "xx"

        for face in self.faces:
            normal = face.normal
            fbits = struct.pack(ffmt, face.incidentEdge.edge.index,
                    face.uvs[0],face.uvs[1],face.uvs[2],
                    normal[0], normal[1], normal[2])
            self.ofile.write(fbits)
            
    
    def write_uvs(self):
        uvfmt = "HHHxx"
        for uv in self.uvlist:
            uvbits = struct.pack(uvfmt, uv[0], uv[1], uv[2])
            self.ofile.write(uvbits)


    def write(self):
        print("Writting header...\n")
        self.write_header()
        print("Writting " + str(len(self.verts)) + " verticies\n")
        self.write_verts()
        print("Writting " + str(len(self.edges)) + " edges\n")
        self.write_edges()
        print("Writting " + str(len(self.faces)) + " faces\n")
        self.write_faces()
        print("Writting " + str(len(self.uvlist)) + " uvs\n")
        self.write_uvs()

    
    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        self.ofile = open(self.filepath, "wb")
        self.write()
        self.ofile.close()
        return {"FINISHED"}




def menu_func_export(self, context):
    self.layout.operator(MDL.bl_idname, text="Custom Model (.mdl)")


def register():
    bpy.utils.register_class(MDL)
    bpy.types.INFO_MT_file_export.append(menu_func_export)

def unregister():
    bpy.utils.unregister_class(MDL)
    bpy.types.INFO_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
    register()
    bpy.ops.export.mdl2('INVOKE_DEFAULT')
