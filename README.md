# Blender Export Suite

A suite of export scripts for a set of custom file formats. The scripts allow for
exporting of various data from the 'Blender' 3D modeling software.

All formats contain a specification in the header of the export script.

### Formats

#### SCN

A scene file format designed to contain a heirarchical set of packed data in various formats.
The scene format is seperated into packed data (Models, Textures, etc) and entity information
(information on individual instances of a scene)

#### MDL
A 3D model file format. Contains a set of verticies, and faces in the form of 
indices into the vertex array. Each vertex contains a position, normal, uv coordinate,
and some other information for materials and armature skinning. Each face is a triangle.
The format is designed to be trivial load from file and upload to the GPU for future rendering.

#### POS
A mesh pose file format. contains information on a set of heirarchical bones, as well as
a set of poses for the bones. The poses are intended to be keyframes to be interpolated between,
but may be used as animations.

#### CAM
A file format to contain the metadata on a scene's camera 
Meant to be embedded within a SCN file.
TODO

#### LMP
A file format to represent different lamps within a scene.
Meant to be embedded within a SCN file.
TODO
