import os
import clr
clr.AddReference("System")
clr.AddReference("System.Data.Sqlite")
clr.AddReference("Newtonsoft.Json")
from System.Net import HttpListener
from System.IO import StreamReader, StreamWriter
import json
import System
import math
import Rhino.Geometry as rg
from System import Guid
from Rhino.Geometry import Plane, Brep, Mesh, Curve, Box, Point3d, Vector3d, Interval
from System.Drawing import Color
# Newtonsoft dll is in the same folder
import Newtonsoft.Json
from Newtonsoft.Json import JsonConvert
from System.Data.SQLite import SQLiteConnection
from Rhino.FileIO import SerializationOptions
import rhinoscriptsyntax as rs


from TimberBranch import TimberBranch

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
    def get_placement_with_id(db_path, id):
        plane_data = None
        connection_string = "Data Source='{}';Version=3;".format(db_path)
    
        with SQLiteConnection(connection_string) as connection:
            connection.Open()
            with connection.CreateCommand() as select_command:
                select_command.CommandText = "SELECT placementPlane FROM GEOMETRIES WHERE ID = @id"
                select_command.Parameters.AddWithValue("@id", id)
    
                with select_command.ExecuteReader() as reader:
                    if reader.Read():
                        plane_data = reader.GetString(0)
    
        rh_plane = sqlite_db.string_to_plane(plane_data) if plane_data else None
        return rh_plane

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


def get_proper_plane_for_point(plane, input_plane,offset):
    pnt = input_plane.Origin
    pl2 = rg.Plane(plane)
    pl2.Rotate(math.pi / 2, plane.YAxis, plane.Origin)

    high_dot = float('-inf')
    best = rg.Plane.Unset
    vec = pnt - plane.Origin

    

    for i in range(4):
        pl3 = rg.Plane(plane)
        pl3.Rotate(math.pi / 2 * i, plane.YAxis, plane.Origin)
        
        dot = vec * pl3.ZAxis
        if dot > high_dot:
            high_dot = dot
            best = pl3

    projection = best.ClosestPoint(pnt) + best.ZAxis * offset

    planar_trs = rg.Transform.PlanarProjection(best)
    input_plane.Transform(planar_trs)

    final = rg.Plane(projection, input_plane.XAxis, input_plane.YAxis)
    final.Origin = projection

    return final


def get_proper_plane_aligned(plane, input_plane,offset = 18):
    
    dist_0, dist_dif_0 = pnt_z_distance(plane, input_plane)
    
    plane01 = Plane(input_plane)
    plane02 = Plane(input_plane)
    
    plane01.Translate(plane01.ZAxis * dist_dif_0)
    plane02.Translate(plane02.ZAxis * -dist_dif_0)
    
    
    temp, dif_1 = pnt_z_distance(plane,plane01)
    temp, dif_2 = pnt_z_distance(plane,plane02)
    
    if dif_1 < 0.0001:
        return plane01
    else:    
        return plane02

def pnt_z_distance(plane, input_plane,offset = 18):
    
    target_og = plane.Origin
    projected_tgt = input_plane.ClosestPoint(target_og)
    
    dist = target_og.DistanceTo(projected_tgt)
    dist_dif = abs(offset - dist)
    return dist, dist_dif


def get_proper_plane_from_quaternion(q_x, q_y, q_z, q_w, p_x, p_y, p_z):
    plane = rg.Plane.WorldZX
    
    quaternion = rg.Quaternion(q_y, q_w, q_z, q_x)
    
    transform_box = clr.StrongBox[rg.Transform](rg.Transform.Unset)
    success = quaternion.GetRotation(transform_box)

    if success:
        plane.Transform(transform_box.Value)

    plane.Origin = rg.Point3d(p_x, p_y, p_z)

    return plane


# Create and configure the HttpListener
listener = HttpListener()
listener.Prefixes.Add("http://127.0.0.1:5632/")
listener.Start()

print("IronPython HTTP Server is running on http://192.168.1.101:5632/")

try:
    while True:
        context = listener.GetContext()  # Wait for a request
        request = context.Request
        response = context.Response
        response.AddHeader("Access-Control-Allow-Origin", "https://rhino_web.remosharp.com")
        response.AddHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        response.AddHeader("Access-Control-Allow-Headers", "Content-Type")
        
        
        # Handle preflight OPTIONS request
        if request.HttpMethod == "OPTIONS":
            response.StatusCode = 200  # OK
            response.ContentLength64 = 0
            response.OutputStream.Close()
            continue  # Skip the rest and wait for another request
        
        
        # Check if it's a POST request
        if request.HttpMethod == "POST":
            try:
                # Read and parse the JSON payload
                reader = StreamReader(request.InputStream, request.ContentEncoding)
                json_data = reader.ReadToEnd()
                reader.Close()

                data = json.loads(json_data)  # Parse JSON
                # print("Received JSON:", data)

                # Construct a response
                
                plane = sqlite_db.string_to_plane(data["placementPlane"])
                designer = data["designer"]
                color = sqlite_db.string_to_rgb(data["color"])
                parentID = data["parentID"]
                
                stop_server = data["stop_server"] if "stop_server" in data else []
                
                if stop_server == "akhajsourcereposSQLiteRhi":
                    response.StatusCode = 200  # OK
                    response.ContentLength64 = 0
                    listener.Stop()
                
                
                db_path = r"C:\Projects\repos\SQLiteRhinoDBServer\bin\Debug\GHDB.db"
                if sqlite_db.db_exists(db_path):
                    # get the parent branch
                    parent_plane = sqlite_db.get_placement_with_id(db_path,parentID)
                    
                    # get the proper plane for the parent branch
                    # proper_plane = get_proper_plane_for_point(plane, parent_plane,18)
#                    proper_plane = get_proper_plane_from_quaternion(data["q_x"],data["q_y"],data["q_z"],data["q_w"],data["p_x"],data["p_y"],data["p_z"])
                    
                    proper_plane = get_proper_plane_aligned(parent_plane, plane,18)
                    
                    get_proper_plane_aligned

                    branch = TimberBranch(placement_plane=proper_plane , user=designer, color=color, state="virtual", branch=None, parentIDs=[parentID])

                    dics = "temp"
                    sqlite_db.save_stick_to_db(True,[branch],db_path)
                
                
                # Send response
                result ={
                    "status": "success",
                    "message": "Branch created successfully",
                    "branch_id": branch.ID.ToString()
                }
                
                response_json = json.dumps(result)
                response.StatusCode = 200  # OK
                response.ContentType = "application/json"
                response.ContentLength64 = len(response_json)
                writer = StreamWriter(response.OutputStream)
                
                writer.Write(response_json)
                writer.Flush()
                response.OutputStream.Close()

            except Exception as e:
                # Handle JSON errors
                error_response = {"status": "error", "message": str(e)}
                response_json = json.dumps(error_response)
                response.StatusCode = 400  # Bad request
                response.ContentType = "application/json"
                response.ContentLength64 = len(response_json)
                writer = StreamWriter(response.OutputStream)
                writer.Write(response_json)
                writer.Flush()
                response.OutputStream.Close()

        else:
            # Handle unsupported request methods
            response.StatusCode = 405  # Method Not Allowed
            response.ContentLength64 = 0
            response.OutputStream.Close()
    listener.Stop()

except KeyboardInterrupt:
    print("\nShutting down server...")
    listener.Stop()
