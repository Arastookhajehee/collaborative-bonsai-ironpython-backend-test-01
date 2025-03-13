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
from System.Threading import ThreadPool, WaitCallback

# using IronPython, set a websocket client
clr.AddReference("WebsocketSharp.Core")
from WebSocketSharp import WebSocket

# Create a WebSocket client
ws = WebSocket("ws://127.0.0.1:12541/")  # replace with your WebSocket server URL

# Define event handlers
def on_open(sender, e):
    print("Connected to the server.")

def on_message(sender, e):
    # e.Data holds the received message.
    print("Received message: {0}".format(e.Data))

def on_error(sender, e):
    print("Error: {0}".format(e.Message))

def on_close(sender, e):
    print("Connection closed. Code: {0}, Reason: {1}".format(e.Code, e.Reason))


def plane_from_csv(csv):
    parts = csv.split(',')
    pnt = rg.Point3d(float(parts[0]),float(parts[1]),float(parts[2]))
    vec1 = rg.Vector3d(float(parts[3]),float(parts[4]),float(parts[5]))
    vec2 = rg.Vector3d(float(parts[6]),float(parts[7]),float(parts[8]))

    return rg.Plane(pnt,vec1,vec2)

def PlaneToStick(placementPlane):
    width = 18;
    length = 300;
    thickness = 18;
    xInterval = rg.Interval(-width / 2, width / 2);
    yInterval = rg.Interval(-length / 2, length / 2);
    zInterval = rg.Interval(-thickness / 2, thickness / 2);
    stick = rg.Box(placementPlane, xInterval, yInterval, zInterval).ToBrep();
    return stick

def StickToPlane(stick):
    sorted_faces = SortStickFaces(stick)
    sides = GetSides(sorted_faces)
    tips = GetTips(sorted_faces)
    stick_plane = GetStickPlane(sides, tips)
    rotated_stick_plane = rg.Plane(stick_plane.Origin, stick_plane.XAxis, stick_plane.ZAxis)
    return rotated_stick_plane

def ScaleLine(line, factor):
    linevec = rg.Vector3d(line[1]-line[0])
    linemid = (line[0]+line[1])/2
    lineplane = rg.Plane(linemid,rg.Plane.WorldXY.ZAxis)
    line.Transform(rg.Transform.Scale(lineplane,factor,factor,factor))

def SortStickFaces(stick):
    faces = stick.Faces
    areas=[rg.AreaMassProperties.Compute(face).Area for face in faces]
    faces_and_areas = zip(faces,areas)
    sorted_faces = sorted(faces_and_areas, key=lambda x: x[1])
    return sorted_faces

def GetSides(sorted_faces):
    sides = [face[0] for face in sorted_faces[2:]]
    return sides

def GetTips(sorted_faces):
    tips = [face[0] for face in sorted_faces[:2]]
    return tips

def GetThickness(tips):
    area = rg.AreaMassProperties.Compute(tips[0]).Area
    thickness = math.sqrt(area)
    return thickness

def GetLength(tips):
    top = rg.AreaMassProperties.Compute(tips[0]).Centroid
    bottom = rg.AreaMassProperties.Compute(tips[1]).Centroid
    length = top.DistanceTo(bottom)
    return length

def GetStickPlane(sides, tips):
    top = rg.AreaMassProperties.Compute(tips[0]).Centroid
    bottom = rg.AreaMassProperties.Compute(tips[1]).Centroid
    center = (top+bottom)/2
    z_axis = rg.Vector3d(top-bottom)
    x_axis = sides[0].NormalAt(0,0)
    y_axis = rg.Vector3d.CrossProduct(z_axis, x_axis)
    plane = rg.Plane(center,x_axis,y_axis)
    return plane

def GetSidePlane(sides, side_id, stick_plane):
    side = sides[side_id]
    center = rg.AreaMassProperties.Compute(side).Centroid
    x_axis = stick_plane.ZAxis
    z_axis = side.NormalAt(0,0)
    y_axis = rg.Vector3d.CrossProduct(z_axis, x_axis)
    plane = rg.Plane(center,x_axis,y_axis)
    return plane

def GetSharedPlane(side_plane_a, side_plane_b, shift_ab):
    shared_line = rg.Intersect.Intersection.PlanePlane(side_plane_a,side_plane_b)[1]
    ScaleLine(shared_line,100)
    shared_vector = rg.Vector3d(shared_line[1]-shared_line[0])
    shared_vector.Unitize()
    shared_line = shared_line.ToNurbsCurve()
    shared_line.Domain = rg.Interval(0,1)
    shared_plane = rg.Plane(shared_line.PointAt(shift_ab),shared_vector)
    return shared_plane
    
def GetSharedLine(side_plane_a, side_plane_b, shift_ab):
    shared_line = rg.Intersect.Intersection.PlanePlane(side_plane_a,side_plane_b)[1]
    ScaleLine(shared_line,100)
    shared_vector = rg.Vector3d(shared_line[1]-shared_line[0])
    shared_vector.Unitize()
    shared_line = shared_line.ToNurbsCurve()
    shared_line.Domain = rg.Interval(0,1)
    return shared_line

def CreateNewStick(stick, stick_plane, side_plane, shared_plane, shared_line, thickness, length, flip, shift):
    line = rg.Intersect.Intersection.PlanePlane(shared_plane,side_plane)[1]
    ScaleLine(line,100)
    overlap = rg.Intersect.Intersection.CurveBrep(line.ToNurbsCurve(),stick,0.0001)[1]
    if len(overlap)>0:
        point = (overlap[0].PointAtStart+overlap[0].PointAtEnd)/2
    else: point = (line[0]+line[1])/2
    point = (point+shared_plane.Origin)/2
    vector = rg.Vector3d(shared_line.PointAtEnd-shared_line.PointAtStart)
    new_stick_plane = rg.Plane(point,vector,side_plane.ZAxis)
    new_stick = stick.Duplicate()
    new_stick.Transform(rg.Transform.PlaneToPlane(stick_plane,new_stick_plane))
    new_stick.Transform(rg.Transform.Translation(thickness/2*new_stick_plane.YAxis))
    new_stick.Transform(rg.Transform.Translation(flip*thickness/2*shared_plane.ZAxis))
    new_stick.Transform(rg.Transform.Translation(length*shift*new_stick_plane.ZAxis))
    return new_stick

def AdjustP1(sides,side_id,shared_plane):
    face = sides[side_id]
    edge = face.OuterLoop.To3dCurve()
    segments = edge.DuplicateSegments()
    vertices = [segment.PointAtStart for segment in segments]
    distances = [vertice.DistanceTo(rg.Plane.ClosestPoint(shared_plane, vertice)) for vertice in vertices]
    return (min(distances), max(distances))

def GenerateLink(stick_a,stick_b,side_id_a,side_id_b, shift_ab, flip, shift_a, shift_b):

    # Get Planes
    sorted_faces_a = SortStickFaces(stick_a)
    sides_a = GetSides(sorted_faces_a)
    tips_a = GetTips(sorted_faces_a)
    sorted_faces_b = SortStickFaces(stick_b)
    sides_b = GetSides(sorted_faces_b)
    tips_b = GetTips(sorted_faces_b)
    thickness_a = GetThickness(tips_a)
    length_a = GetLength(tips_a)
    thickness_b = GetThickness(tips_b)
    length_b = GetLength(tips_b)
    stick_plane_a = GetStickPlane(sides_a, tips_a)
    center_a = stick_plane_a.Origin
    stick_plane_b = GetStickPlane(sides_b, tips_b)
    center_b = stick_plane_b.Origin
    side_plane_a = GetSidePlane(sides_a, side_id_a, stick_plane_a)
    side_plane_b = GetSidePlane(sides_b, side_id_b, stick_plane_b)
    temp=(side_plane_a,side_plane_b)
    
    shared_plane = GetSharedPlane(side_plane_a, side_plane_b, 0)
    shared_line = GetSharedLine(side_plane_a, side_plane_b, 0)

    # Adjust P1
    min_distance_a = AdjustP1(sides_a,side_id_a,shared_plane)[0]
    max_distance_a = AdjustP1(sides_a,side_id_a,shared_plane)[1]
    min_distance_b = AdjustP1(sides_b,side_id_b,shared_plane)[0]
    max_distance_b = AdjustP1(sides_b,side_id_b,shared_plane)[1]
    min_distance = max((min_distance_a, min_distance_b))
    max_distance = min((max_distance_a, max_distance_b))
    translation = shift_ab*min_distance+(1-shift_ab)*max_distance
    shared_plane.Translate(translation*shared_plane.ZAxis)

    # Create sticks
    if flip is True: flip = 1
    else: flip = -1
    stick_c = CreateNewStick(stick_a, stick_plane_a, side_plane_a, shared_plane, shared_line, thickness_a, length_a, flip, shift_a)
    stick_d = CreateNewStick(stick_b, stick_plane_b, side_plane_b, shared_plane, shared_line, thickness_b, length_b, -flip, shift_b)
    #return stick_c, stick_d, shared_line, stick_line_c, stick_line_d
    return (stick_c, stick_d)

def process_planes(branch_a, branch_b, shift_ab, shift_a, shift_b):
    vec1 = branch_a.ZAxis
    vec2 = branch_b.ZAxis
    errors_txt = []
    #print vec1.IsParallelTo(vec2, 0.01)
    #print vec1.IsPerpendicularTo(vec2, 0.01)
    #if vec1.IsParallelTo(vec2, 0.01) == 0 or vec1.IsPerpendicularTo(vec2, 0.01) is False:
    stick_a = PlaneToStick(branch_a)
    stick_b = PlaneToStick(branch_b)
    sorted_faces_a = SortStickFaces(stick_a)
    sides_a = GetSides(sorted_faces_a)
    tips_a = GetTips(sorted_faces_a)
    thickness_a = GetThickness(tips_a)
    length_a = GetLength(tips_a)
    min_glue_area = thickness_a**2
    configurations = []
    for i in range(4): # 4 sides_a
        for j in range(4): # 4 sides_b
            for k in [True, False]: # flip = True or False
                try:
                    configurations.append(GenerateLink(stick_a,stick_b,i,j, shift_ab, k, shift_a, shift_b))
                except:
                    configurations.append(None)
    valid_configurations = []
    other_configurations = []
    valid_ids = []
    n=0
    for configuration in configurations:
        if configuration != None:
            stick_c, stick_d = configuration[0:2]
            temp = stick_c, stick_d
            flag = False
            if len(rg.Intersect.Intersection.BrepBrep(stick_a, stick_d, 0.001)[1]) == 0:
                if len(rg.Intersect.Intersection.BrepBrep(stick_b, stick_c, 0.001)[1]) == 0:
                    if len(rg.Intersect.Intersection.BrepBrep(stick_c, stick_d, 0.001)[1]) > 0:
                        if len(rg.Intersect.Intersection.BrepBrep(stick_a, stick_c, 0.001)[1]) > 0:
                            if len(rg.Intersect.Intersection.BrepBrep(stick_b, stick_d, 0.001)[1]) > 0:
                                cd = rg.Brep.CreatePlanarBreps(rg.Curve.JoinCurves(rg.Intersect.Intersection.BrepBrep(stick_c, stick_d, 0.001)[1]))
                                ac = rg.Brep.CreatePlanarBreps(rg.Curve.JoinCurves(rg.Intersect.Intersection.BrepBrep(stick_a, stick_c, 0.001)[1]))
                                bd = rg.Brep.CreatePlanarBreps(rg.Curve.JoinCurves(rg.Intersect.Intersection.BrepBrep(stick_b, stick_d, 0.001)[1]))
                                if cd is not None and ac is not None and bd is not None:
                                    if rg.AreaMassProperties.Compute(cd).Area > min_glue_area and rg.AreaMassProperties.Compute(ac).Area > min_glue_area and rg.AreaMassProperties.Compute(bd).Area > min_glue_area:
                                            valid_configurations.append(configuration)
                                            valid_ids.append(n)
                                            flag = True
                                            errors_txt.append(None)
                                    else: errors_txt.append("insufficient contact")
                                else: errors_txt.append("insufficient contact")
                            else: errors_txt.append("no contact")
                        else: errors_txt.append("no contact")
                    else: errors_txt.append("no contact")
                else: errors_txt.append("collision")
            else: errors_txt.append("collision")
            if flag is False:
                other_configurations.append(configuration)
        n+=1
    #else: errors_txt.append("Coplanar sticks...")
    return valid_configurations, configurations, valid_ids, errors_txt

def StickToPlane(stick):
    sorted_faces = SortStickFaces(stick)
    sides = GetSides(sorted_faces)
    tips = GetTips(sorted_faces)
    stick_plane = GetStickPlane(sides, tips)
    rotated_stick_plane = rg.Plane(stick_plane.Origin, stick_plane.XAxis, stick_plane.ZAxis)
    return rotated_stick_plane

def SortStickFaces(stick):
    faces = stick.Faces
    areas=[rg.AreaMassProperties.Compute(face).Area for face in faces]
    faces_and_areas = zip(faces,areas)
    sorted_faces = sorted(faces_and_areas, key=lambda x: x[1])
    return sorted_faces

def GetSides(sorted_faces):
    sides = [face[0] for face in sorted_faces[2:]]
    return sides

def GetTips(sorted_faces):
    tips = [face[0] for face in sorted_faces[:2]]
    return tips

def GetStickPlane(sides, tips):
    top = rg.AreaMassProperties.Compute(tips[0]).Centroid
    bottom = rg.AreaMassProperties.Compute(tips[1]).Centroid
    center = (top+bottom)/2
    z_axis = rg.Vector3d(top-bottom)
    x_axis = sides[0].NormalAt(0,0)
    y_axis = rg.Vector3d.CrossProduct(z_axis, x_axis)
    plane = rg.Plane(center,x_axis,y_axis)
    return plane

def process_sticks(run, only_valid, valid_configurations, configurations,valid_ids,errors_txt, browse=0):
    if run:
        #if errors_txt[0] != "Coplanar sticks...":
        if only_valid:
            if len(valid_configurations) > 0:
                browse = browse%len(valid_configurations)
                stick_c, stick_d = valid_configurations[browse]
                plane_c = StickToPlane(stick_c)
                plane_d = StickToPlane(stick_d)
                conf_id = "configuration number: "+ str(valid_ids[browse])
                return plane_c, plane_d
            else:
                conf_id = "no valid configurations"
                return None, None
        
        else:
            stick_c, stick_d = configurations[browse]
            plane_c = StickToPlane(stick_c)
            plane_d = StickToPlane(stick_d)
            return plane_c, plane_d
            print(errors_txt[browse])
        #else:
            #print(errors_txt[0])
            #plane_c=branch_a.placementPlane
            #plane_d=branch_b.placementPlane
    else:
        conf_id = "please select two sticks"

def csv_from_plane(plane01):
    plane01csv = str.format(
        "{},{},{},{},{},{},{},{},{}",
        plane01.Origin.X, 
        plane01.Origin.Y, 
        plane01.Origin.Z, 
        plane01.XAxis.X, 
        plane01.XAxis.Y, 
        plane01.XAxis.Z, 
        plane01.YAxis.X, 
        plane01.YAxis.Y, 
        plane01.YAxis.Z, 
    )
    return plane01csv

def process_bridge(branch_a_csv, branch_b_csv, shift_ab= -4.95, shift_a = 0.146, shift_b= -0.186,browse = 0,only_valid = False):
    branch_a = plane_from_csv(branch_a_csv)
    branch_b = plane_from_csv(branch_b_csv)
    valid_configurations, configurations, valid_ids, errors_txt = process_planes(branch_a, branch_b, shift_ab, shift_a, shift_b)
    plane_c, plane_d = process_sticks(True, only_valid, valid_configurations, configurations,valid_ids,errors_txt, browse)
    
    return plane_c, plane_d




# Hook up the event handlers
ws.OnOpen += on_open
ws.OnMessage += on_message
ws.OnError += on_error
ws.OnClose += on_close

# Connect to the WebSocket server
ws.Connect()

# Send an initial message (for example, a "ping" or your request)
ws.Send("ping")




from TimberBranch import TimberBranch




def send_data_to_websocket(ws_client, id, width, length, thickness, placement_plane,
                                 duplicate_plane, orientable_planes, mesh_box, user, color, state,
                                 parent_ids, child_ids, selected, build_on_plane, message,
                                 design_time_stamp, modification_time_stamp, physical_time_stamp,
                                 fabricated_time_stamp, fabrication_fail, placement_glue_shift,
                                 placement_shift, designer):
    data = {
        "type": "InsertData",
        "ID": id, "width": width, "length": length, "thickness": thickness,
        "placementPlane": placement_plane, "duplicatePlane": duplicate_plane,
        "orientablePlanes": orientable_planes, "meshBox": mesh_box, "user": user,
        "color": color, "state": state, "parentIDs": parent_ids, "childIDs": child_ids,
        "selected": selected, "buildOnPlane": build_on_plane, "message": message,
        "designTimeStamp": design_time_stamp, "modificationTimeStamp": modification_time_stamp,
        "physicalTimeStamp": physical_time_stamp, "fabricatedTimeStamp": fabricated_time_stamp,
        "fabricationFail": fabrication_fail, "placementGlueShift": placement_glue_shift,
        "placementShift": placement_shift, "designer": designer
    }

    ws_client.Send(json.dumps(data))
    print("Data sent to WebSocket server.")



class sqlite_db:
    
    @staticmethod
    def db_exists(path):
        return os.path.exists(path)
    
    @staticmethod
    def save_stick_to_db(save, t_branch, db_path):
        # connection = SQLiteConnection("Data Source='{}';Version=3;".format(db_path))
        # connection.Open()
        
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
                send_data_to_websocket(
                    ws, str(s.ID), s.width, s.length, s.thickness,
                    sqlite_db.plane_to_string(s.placementPlane), sqlite_db.plane_to_string(s.placementPlane), "",
                    new_ms_box.ToJSON(op), s.user, sqlite_db.rgb_to_string(s.color), s.state, "", "",
                    s.selected, sqlite_db.plane_to_string(s.buildOnPlane), s.message, s.designTimeStamp,
                    s.modificationTimeStamp, s.physicalTimeStamp, s.fabricatedTimeStamp,
                    s.fabricationFail, s.placementGlueShift, s.placementShift, s.user
                )
        # connection.Close()
    
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

def MakeBranchFromData(data,db_path):
    plane = sqlite_db.string_to_plane(data["placementPlane"])
    designer = data["designer"]
    color = sqlite_db.string_to_rgb(data["color"])
    parentID = data["parentID"]
    
    
    
    if sqlite_db.db_exists(db_path):
        # get the parent branch
        parent_plane = sqlite_db.get_placement_with_id(db_path,parentID)
        
        # get the proper plane for the parent branch
        # proper_plane = get_proper_plane_for_point(plane, parent_plane,18)
#                    proper_plane = get_proper_plane_from_quaternion(data["q_x"],data["q_y"],data["q_z"],data["q_w"],data["p_x"],data["p_y"],data["p_z"])
        
        proper_plane = get_proper_plane_aligned(parent_plane, plane,18)
        
        
        branch = TimberBranch(placement_plane=proper_plane , user=designer, color=color, state="virtual", branch=None, parentIDs=[parentID])
        branch.ID = data["ID"]
        return branch

def MakeBridgeFromData(data,db_path):
    plane_01 = sqlite_db.string_to_plane(data["plane_03"])
    plane_02 = sqlite_db.string_to_plane(data["plane_04"])
    designer = data["designer"]
    color = sqlite_db.string_to_rgb(data["color"])
    parentID_01 = data["parent_ID_01"]
    parentID_02 = data["parent_ID_02"]
    
    
    
    if sqlite_db.db_exists(db_path):
        # get the parent branch
        parent_plane_01 = sqlite_db.get_placement_with_id(db_path,parentID_01)
        parent_plane_02 = sqlite_db.get_placement_with_id(db_path,parentID_02)
        
        # get the proper plane for the parent branch
        # proper_plane = get_proper_plane_for_point(plane, parent_plane,18)
#                    proper_plane = get_proper_plane_from_quaternion(data["q_x"],data["q_y"],data["q_z"],data["q_w"],data["p_x"],data["p_y"],data["p_z"])
        
        proper_plane_01 = get_proper_plane_aligned(parent_plane_01, plane_01,18)
        proper_plane_02 = get_proper_plane_aligned(parent_plane_02, plane_02,18)
        
        
        branch_01 = TimberBranch(placement_plane=plane_01 , user=designer, color=color, state="virtual", branch=None, parentIDs=[parentID_01])
        branch_02 = TimberBranch(placement_plane=plane_02 , user=designer, color=color, state="virtual", branch=None, parentIDs=[parentID_02])
        branch_01.ID = data["ID_01"]
        branch_02.ID = data["ID_02"]
        return [branch_01,branch_02]

def process_message(context):
    request = context.Request
    response = context.Response
    response.AddHeader("Access-Control-Allow-Origin", "https://bonsai.remosharp.com")
    response.AddHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    response.AddHeader("Access-Control-Allow-Headers", "Content-Type")
    
    
    # Handle preflight OPTIONS request
    if request.HttpMethod == "OPTIONS":
        response.StatusCode = 200  # OK
        response.ContentLength64 = 0
        response.OutputStream.Close()
        return  # Skip the rest and wait for another request
    
    
    # Check if it's a POST request
    if request.HttpMethod == "POST":
        try:
            # Read and parse the JSON payload
            reader = StreamReader(request.InputStream, request.ContentEncoding)
            json_data = reader.ReadToEnd()
            reader.Close()
            data = json.loads(json_data)  # Parse JSON
            # print("Received JSON:", data)
            stop_server = data["stop_server"] if "stop_server" in data else []
            
            
            
            if stop_server == "akhajsourcereposSQLiteRhi":
                response.StatusCode = 200  # OK
                response.ContentLength64 = 0
                listener.Stop()
                return
            # Construct a response
            message_type = data["type"]
            db_path = r"D:\Projects\source\repos\collaborative-bonsai-node-backend-test-01\Bonsai.db"
            if (message_type == "BridgeRequest"):
                
                designer = data["designer"]
                register = data["register"]
                color = sqlite_db.string_to_rgb(data["color"])
                
                
                if not register:
                    # get many possible solutions
                    # a range between -2.50 and 2.50
                    plane_c, plane_d = process_bridge(
                                    data["plane_01"],
                                    data["plane_02"],
                                    data["shift_ab"],
                                    data["shift_a"],
                                    data["shift_b"],
                                    data["browse"],
                                    data["only_valid"]
                                    )
                    
                    plane_c_CSV = csv_from_plane(plane_c)
                    plane_d_CSV = csv_from_plane(plane_d)
                    
                    data["plane_03"] = plane_c_CSV
                    data["plane_04"] = plane_d_CSV
                    
                    response_json = json.dumps(data)
                    response.StatusCode = 200  # OK
                    response.ContentType = "application/json"
                    response.ContentLength64 = len(response_json)
                    writer = StreamWriter(response.OutputStream)
                    
                    writer.Write(response_json)
                    writer.Flush()
                    response.OutputStream.Close()
                else:
                    
                    bridge = MakeBridgeFromData(data,db_path)
                    sqlite_db.save_stick_to_db(True,bridge,db_path)
                    
                    
                    # Send response
                    result ={
                        "status": "success",
                        "message": "bridge created successfully"
                    }
                    
                    response_json = json.dumps(result)
                    response.StatusCode = 200  # OK
                    response.ContentType = "application/json"
                    response.ContentLength64 = len(response_json)
                    writer = StreamWriter(response.OutputStream)
                    
                    writer.Write(response_json)
                    writer.Flush()
                    response.OutputStream.Close()
                    
                    ws.Send("update_all")
            else:
                plane = sqlite_db.string_to_plane(data["placementPlane"])
                designer = data["designer"]
                color = sqlite_db.string_to_rgb(data["color"])
                parentID = data["parentID"]
                

                
                
                if sqlite_db.db_exists(db_path):
                    # get the parent branch
                    parent_plane = sqlite_db.get_placement_with_id(db_path,parentID)
                    
                    # get the proper plane for the parent branch
                    # proper_plane = get_proper_plane_for_point(plane, parent_plane,18)
#                    proper_plane = get_proper_plane_from_quaternion(data["q_x"],data["q_y"],data["q_z"],data["q_w"],data["p_x"],data["p_y"],data["p_z"])
                    
                    proper_plane = get_proper_plane_aligned(parent_plane, plane,18)
                    
                    
                    branch = TimberBranch(placement_plane=proper_plane , user=designer, color=color, state="virtual", branch=None, parentIDs=[parentID])
                    branch.ID = data["ID"]
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
                
                ws.Send("update_all")

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




try:
    while True:
        context = listener.GetContext()  # Wait for a request
        ThreadPool.QueueUserWorkItem(WaitCallback(process_message), context)
    listener.Stop()

except KeyboardInterrupt:
    print("\nShutting down server...")
    listener.Stop()
