import clr
import System
import os
clr.AddReference("System.Data.Sqlite")
clr.AddReference("Newtonsoft.Json")

from System.Data.SQLite import SQLiteConnection
from System.Drawing import Color
from Rhino.Geometry import Mesh, Box, Plane, Point3d, Vector3d, Interval
from Rhino.FileIO import SerializationOptions
import Newtonsoft.Json
class sqlite_db:
    
    @staticmethod
    def db_exists(path):
        return os.path.exists(path)
    
    @staticmethod
    def save_stick_to_db(save, t_branch, db_path):
        connection = SQLiteConnection("Data Source='{}';Version=3;".format(db_path))
        connection.Open()
        
        new_meshes = []
        
        for item in t_branch:
            s = item
            op = SerializationOptions()
            
            ms_box = s.meshBox
            ms_box.Flip(True, True, True)
            
            iv_x = Interval(-150, 150)
            iv_yz = Interval(-9, 9)
            bx = Box(s.placementPlane, iv_yz, iv_x, iv_yz)
            
            new_ms_box = Mesh.CreateFromBox(bx, 3, 18, 3)
            new_meshes.append(new_ms_box)
            
            if save:
                sqlite_db.insert_data(
                    connection, str(s.ID), s.width, s.length, s.thickness,
                    sqlite_db.plane_to_string(s.placementPlane), sqlite_db.plane_to_string(s.placementPlane), "",
                    new_ms_box.ToJSON(op), s.user, sqlite_db.rgb_to_string(s.color), s.state, "", "",
                    s.selected, sqlite_db.plane_to_string(s.buildOnPlane), s.message, s.designTimeStamp,
                    s.modificationTimeStamp, s.physicalTimeStamp, s.fabricatedTimeStamp,
                    s.fabricationFail, s.placementGlueShift, s.placementShift, s.user
                )
        connection.Close()
    
    @staticmethod
    def plane_to_string(plane):
        og = plane.Origin
        vec_x = plane.XAxis
        vec_y = plane.YAxis
        return "{},{},{},{},{},{},{},{},{}".format(og.X, og.Y, og.Z, vec_x.X, vec_x.Y, vec_x.Z, vec_y.X, vec_y.Y, vec_y.Z)
    
    @staticmethod
    def string_to_plane(plane_str):
        plane = plane_str.split(",")
        origin = Point3d(float(plane[0]), float(plane[1]), float(plane[2]))
        x_axis = Vector3d(float(plane[3]), float(plane[4]), float(plane[5]))
        y_axis = Vector3d(float(plane[6]), float(plane[7]), float(plane[8]))
        return Plane(origin, x_axis, y_axis)

    @staticmethod
    def rgb_to_string(color):
        return "{},{},{}".format(color.R, color.G, color.B)
    
    @staticmethod
    def string_to_rgb(color_str):
        rgb = color_str.split(",")
        return Color.FromArgb(int(rgb[0]), int(rgb[1]), int(rgb[2]))
    
    @staticmethod
    def get_placement_with_id(db_path,id):
        connection = SQLiteConnection("Data Source='{}';Version=3;".format(db_path))
        connection.Open()
        plane_data = None
        with connection.CreateCommand() as select_command:
            select_command.CommandText = "SELECT placementPlane FROM GEOMETRIES WHERE ID = @id"
            select_command.Parameters.AddWithValue("@id", id)
            reader = select_command.ExecuteReader()
            if reader.Read():
                plane_data = reader
        connection.Close()
        return plane_data

    @staticmethod
    def insert_data(connection, id, width, length, thickness, placement_plane,
                    duplicate_plane, orientable_planes, mesh_box, user, color, state,
                    parent_ids, child_ids, selected, build_on_plane, message,
                    design_time_stamp, modification_time_stamp, physical_time_stamp,
                    fabricated_time_stamp, fabrication_fail, placement_glue_shift,
                    placement_shift, designer):
        
        with connection.CreateCommand() as insert_command:
            insert_command.CommandText = """
            INSERT INTO GEOMETRIES
            (ID, width, length, thickness, placementPlane, duplicatePlane, orientablePlanes,
            meshBox, user, color, state, parentIDs, childIDs, selected, buildOnPlane,
            message, designTimeStamp, modificationTimeStamp, physicalTimeStamp,
            fabricatedTimeStamp, fabricationFail, placementGlueShift, placementShift, designer)
            VALUES
            (@id, @width, @length, @thickness, @placementPlane, @duplicatePlane, @orientablePlanes,
            @meshBox, @user, @color, @state, @parentIDs, @childIDs, @selected, @buildOnPlane,
            @message, @designTimeStamp, @modificationTimeStamp, @physicalTimeStamp,
            @fabricatedTimeStamp, @fabricationFail, @placementGlueShift, @placementShift, @designer)
            """
            
            params = [
                ("@id", id), ("@width", width), ("@length", length), ("@thickness", thickness),
                ("@placementPlane", placement_plane), ("@duplicatePlane", duplicate_plane),
                ("@orientablePlanes", orientable_planes), ("@meshBox", mesh_box), ("@user", user),
                ("@color", color), ("@state", state), ("@parentIDs", parent_ids), ("@childIDs", child_ids),
                ("@selected", selected), ("@buildOnPlane", build_on_plane), ("@message", message),
                ("@designTimeStamp", design_time_stamp), ("@modificationTimeStamp", modification_time_stamp),
                ("@physicalTimeStamp", physical_time_stamp), ("@fabricatedTimeStamp", fabricated_time_stamp),
                ("@fabricationFail", fabrication_fail), ("@placementGlueShift", placement_glue_shift),
                ("@placementShift", placement_shift), ("@designer", designer)
            ]
            
            for param, value in params:
                insert_command.Parameters.AddWithValue(param, value)
            
            insert_command.ExecuteNonQuery()
