# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 3
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
#
# Copyright (C) 2022 Michael Vigovsky

import os, struct, numpy

import bpy, bpy_extras, mathutils # pylint: disable=import-error

bl_info = {
    "name": "LLM Import",
    "author": "Michael Vigovsky",
    "version": (0, 0, 1),
    "blender": (2, 83, 0),
    "location": "File > Import > Linden Lab Mesh (.llm)",
    "description": "Import Linden Lab .llm files",
    "category": "Import-Export",
}

def readu16(f):
    return struct.unpack("<H", f.read(2))[0]
def readu32(f):
    return struct.unpack("<I", f.read(4))[0]
def readvec(f):
    return struct.unpack("<fff", f.read(12))
def readstr(f, l):
    return f.read(l).split(b'\0')[0]

class OpImportLLM(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    bl_idname = "import_mesh.llm"
    bl_label = "Import LLM"
    bl_description = "Import Linden Lab .llm mesh"
    bl_options = {'UNDO'}

    filter_glob: bpy.props.StringProperty(default="*.llm", options={'HIDDEN'})

    def execute(self, context):
        name = os.path.splitext(os.path.basename(self.filepath))[0]
        with open(self.filepath, "rb") as f:
            if readstr(f, 24) != b"Linden Binary Mesh 1.0":
                self.report({'ERROR'}, "Invalid .llm file")
                return {'CANCELLED'}
            has_weights, has_dtc = f.read(2)
            pos = readvec(f)
            rot = readvec(f)
            _ = f.read(1) # Rotation order, not used in original parser too
            scl = readvec(f)

            cverts = readu16(f)
            verts = numpy.frombuffer(f.read(cverts*12), dtype="<f4").reshape(-1, 3)
            f.seek(cverts*24, 1) # Skipping normals and binormals
            texcoords = numpy.frombuffer(f.read(cverts*8), dtype="<f4").reshape(-1, 2)
            if has_dtc:
                # Skip detail texture coordinates
                f.seek(cverts*8, 1)
            if has_weights:
                weights = numpy.frombuffer(f.read(cverts*4), dtype="<f4")

            faces = numpy.frombuffer(f.read(readu16(f)*6), dtype="<u2").reshape(-1, 3)

            mesh = bpy.data.meshes.new(name)
            mesh.from_pydata(verts, (), faces.tolist())
            mesh.validate()
            mesh.uv_layers.new().data.foreach_set("uv", texcoords[[l.vertex_index for l in mesh.loops]].reshape(-1))

            obj = bpy.data.objects.new(name, mesh)
            obj.location = pos
            obj.rotation_euler = rot
            obj.rotation_mode = 'XYZ'
            obj.scale = scl
            context.collection.objects.link(obj)

            if has_weights:
                #for i in range(readu16(f)):
                #    vg = obj.vertex_groups.new(name=readstr(f, 64).decode("ascii"))
                #    for vi in numpy.where((weights>(i)) & (weights < (i+2)))[0]:
                #        vg.add([int(vi)], 1-abs(i+1-weights[vi]) ,'REPLACE')
                f.seek(readu16(f)*64, 1) # I still can't figure how to match weight painting with joints so skip joint names for now
                i = 0
                while True:
                    indices = numpy.where((weights>(i)) & (weights < (i+2)))[0]
                    if len(indices) == 0:
                        break
                    vg = obj.vertex_groups.new(name=f"W{i}")
                    for vi in indices:
                        vg.add([int(vi)], 1-abs(i+1-weights[vi]) ,'REPLACE')
                    i += 1

            obj.shape_key_add(name="Basis", from_mix=False)
            while True:
                name = readstr(f, 64)
                if not name or name == b"End Morphs":
                    break
                skd = obj.shape_key_add(name=name.decode("ascii"), from_mix=False).data
                for item in struct.iter_unpack("<Ifffffffffff", f.read(readu32(f)*48)):
                    skd[item[0]].co += mathutils.Vector(item[1:4])

        return {'FINISHED'}

    def draw(self, _):
        pass

def menu_import(self, _):
    self.layout.operator("import_mesh.llm", text="Linden Lab Mesh (.llm)")

def register():
    bpy.utils.register_class(OpImportLLM)
    bpy.types.TOPBAR_MT_file_import.append(menu_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    bpy.utils.unregister_class(OpImportLLM)

if __name__ == "__main__":
    register()
