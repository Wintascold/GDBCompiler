#-------------------------------------------------------------------------------
# Name:        Component Map Extractor
# Purpose:
#
# Author:      jrwinter
#
# Created:     05/06/2018
# Copyright:   (c) jrwinter 2018
# Licence:     <your licence>
# Version:     6.2
#-------------------------------------------------------------------------------

# Import system modules
import sys, string, os, arcpy, arcgisscripting, re, shutil
from re import search

GDB_List = arcpy.GetParameterAsText(0).split(";")
Component_Map_Folders_Location = arcpy.GetParameterAsText(1)
MainPolyFC = arcpy.GetParameterAsText(2)
MapInfo = arcpy.GetParameterAsText(3)
MainFC = MainPolyFC[-3:]
gmap_list = []
code_list = []
fourcodelist = []
fc_list = []
fields = ['COMPONENT_MAP', 'GMAP_CODE', 'GMAP_ID']
select = "LBL = ''"
MainPolyFC = str(MainPolyFC.rsplit('\\',1)[1])

expression1 = "setNull(str(!LBL!))"
codeblock1 = """
def setNull(lbl):
        return None
    """

# Copies the compiled map GDB to a temporary xxxx_geology.gdb and deletes topology and tables


for GDB in GDB_List:
    WorkingCompGDB = Component_Map_Folders_Location + "\\xxxx_geology.gdb"
    arcpy.env.workspace = GDB
    arcpy.Copy_management(GDB, WorkingCompGDB)
    arcpy.ExcelToTable_conversion(MapInfo, WorkingCompGDB + "\mapinfotable", '') # Create a geodatabase table of the Map Info so that an Update Cursor can be used
    with arcpy.da.SearchCursor(WorkingCompGDB + "\mapinfotable", fields) as cursor:
        for row in cursor:
            if row[0].lower() == u'yes':
                fourcodelist.append(row[1])
                if ";" in row[2]:
                    x = row[2].split(';')
                    for i in x:
                        y = []
                        y.append(row[1])
                        y.append(i)
                        code_list.append(y)
                        next
                else:
                    code_list.append(row[1:])
        del row
        del cursor

    arcpy.env.workspace = WorkingCompGDB
    fds = arcpy.ListDatasets("*", "All")
    for fd in fds:
        arcpy.env.workspace = fd
        tops = arcpy.ListDatasets("*", "All")
        for top in tops:
            if top.endswith("_topology"):
                arcpy.Delete_management(top)
        fcs = arcpy.ListFeatureClasses()
        for fc in fcs:
            if arcpy.Exists(WorkingCompGDB + "/MAP_" + fc[4:].upper() + "_Relate"):
                arcpy.Delete_management(WorkingCompGDB + "/MAP_" + fc[4:].upper() + "_Relate")
            else:
                next
            if arcpy.Exists(WorkingCompGDB + "/UNIT_" + fc[4:].upper() + "_Relate"):
                arcpy.Delete_management(WorkingCompGDB + "/UNIT_" + fc[4:].upper() + "_Relate")
            else:
                next

    arcpy.env.workspace = WorkingCompGDB
    tables = arcpy.ListTables()
    for table in tables:
        if table == "mapinfotable":
            arcpy.Delete_management(table)

   # Creates a schema that is used to create each component map GDB
    arcpy.ExportXMLWorkspaceDocument_management(WorkingCompGDB, Component_Map_Folders_Location + "\\schema.xml", "SCHEMA_ONLY", "BINARY", "NO_METADATA")

# Deletes quad boundaries and creates new boundaries based off of dissolved (on GMAP_ID) MainPolyFC
arcpy.env.workspace = WorkingCompGDB
fds = arcpy.ListDatasets("*", "Feature")
for fd in fds:
   arcpy.env.workspace = fd
   fcs = arcpy.ListFeatureClasses()
   for fc in fcs:
        if fc.endswith(MainPolyFC):
            arcpy.MakeFeatureLayer_management(fc, fc + "_lay", "", "", "")
            arcpy.Dissolve_management(fc + "_lay", fc + "_dissolve", "GMAP_ID", "", "SINGLE_PART", "DISSOLVE_LINES")
            arcpy.FeatureToLine_management(fc + "_dissolve", fc + "a_f2l", "", "")
            arcpy.Delete_management(fc + "_dissolve")
   for fc in fcs:
        if fc.endswith((MainPolyFC) + "a"):
            arcpy.MakeFeatureLayer_management(fc, fc + "_lay", "", "", "")
            #Deletes existing quad boundaries
            arcpy.SelectLayerByAttribute_management(fc + "_lay", "NEW_SELECTION", '"POS" = 10')
            arcpy.DeleteFeatures_management(fc + "_lay")

            #Feature to line between map boundaries and new boundary
            arcpy.SelectLayerByAttribute_management(fc + "_lay", "NEW_SELECTION", '"POS" = 11')
            arcpy.FeatureToLine_management([fc + "_lay", fc + "_f2l"], fc + "_f2l_new", "", "ATTRIBUTES")
            arcpy.CalculateField_management(fc + "_f2l_new", "GMAP_ID", "!GMAP_ID_1!", "PYTHON_9.3")

            #Deletes existing map boundaries
            arcpy.DeleteFeatures_management(fc + "_lay")
            arcpy.Delete_management(fc + "_lay")

            #Appends new map/quad boundary to glga
            arcpy.Append_management(fc + "_f2l_new", fc, "NO_TEST")

            arcpy.MakeFeatureLayer_management(fc, fc + "_layer", "", "", "")
            arcpy.SelectLayerByAttribute_management(fc + "_layer", "NEW_SELECTION", '"POS" = 0')
            arcpy.CalculateField_management(fc + "_layer", "NOTES", "\"NA\"", "PYTHON_9.3")
            arcpy.CalculateField_management(fc + "_layer", "POS", 10)
            arcpy.CalculateField_management(fc + "_layer", "SYM", "\"31.08_10\"", "PYTHON_9.3")
            arcpy.SelectLayerByAttribute_management(fc + "_layer", "CLEAR_SELECTION")
            arcpy.FeatureToLine_management(fc + "_layer", fc + "_newlay2", "", "ATTRIBUTES")
            arcpy.DeleteFeatures_management(fc + "_layer")
            arcpy.Append_management(fc + "_newlay2", fc, "NO_TEST", "", "")
            arcpy.Delete_management(fc + "_newlay")
            arcpy.Delete_management(fc + "_newlay2")
            arcpy.Delete_management(fc + "_layer")
            arcpy.Delete_management(fc + "_f2l")
            arcpy.Delete_management(fc + "_f2l_new")

# Gets the four letter code of the compiled map
for GDB in GDB_List:
    arcpy.env.workspace = GDB
    fds = arcpy.ListDatasets("*", "Feature")
    for fd in fds:
        compfd = fd
#-------------------Uses the Map Info Spreadsheet to Split Data From Compiled Map to Component Maps-----------#

for code in code_list:
    string = str(code[0])
    newcode = re.sub('[(),]', '', string)
    newcode = newcode.lower()
    if "bedrock" in newcode:
        maptype = "bedrock_geology"
    elif "surficial" in newcode:
        maptype = "surficial_geology"
    elif "glacial" in newcode:
        maptype = "glacial_geology"
    elif "geomorphology" in newcode:
        maptype = "geomorphology"
    elif "geohazard" in newcode:
        maptype = "geohazard"
    elif "benthic" in newcode:
        maptype = "benthic_habitat"
    else:
        maptype = "geology"
    if "_" in newcode:
        newcode = newcode.rsplit('_',1)[0]
        newfd = newcode
    else:
        newfd = newcode
    NewGDB = Component_Map_Folders_Location + '/' + newcode + "_" + maptype + ".gdb"     # Creates Component Map GDBs
    if arcpy.Exists(NewGDB):
        next
    else:
        arcpy.CreateFileGDB_management(Component_Map_Folders_Location, newcode + "_" + maptype + ".gdb", "CURRENT")
        arcpy.ImportXMLWorkspaceDocument_management(NewGDB, Component_Map_Folders_Location + "\\schema.xml", "SCHEMA_ONLY")
        arcpy.Rename_management(Component_Map_Folders_Location + '/' + newcode + "_" + maptype + ".gdb" + "/" + compfd, Component_Map_Folders_Location + '/' + newcode + "_" + maptype + ".gdb" + "/" + newfd) # Renames FDs in each component map
        arcpy.env.workspace = Component_Map_Folders_Location + '/' + newcode + "_" + maptype + ".gdb"
        fds = arcpy.ListDatasets("*", "Feature")
        for fd in fds:  # Renames fcs in each component map
            arcpy.env.workspace = fd
            fcs = arcpy.ListFeatureClasses()
            for fc in fcs:
                arcpy.Rename_management(fc, newfd + fc[4:])

    arcpy.env.workspace = WorkingCompGDB
    fds = arcpy.ListDatasets("*", "Feature")
    for fd in fds:
        arcpy.env.workspace = fd
        fcs = arcpy.ListFeatureClasses()
        for fc in fcs: # Creates temporary shapefiles for each component map
            arcpy.MakeFeatureLayer_management(fc, fc + "_lyr")
            arcpy.SelectLayerByAttribute_management(fc + "_lyr", "NEW_SELECTION", "GMAP_ID = " + code[1])
            selCount = str(arcpy.GetCount_management(fc + "_lyr"))
            if int(selCount) > 0:
                arcpy.CopyFeatures_management(fc + "_lyr", Component_Map_Folders_Location + "/" + newcode + "_" + maptype + "_" + fc) # Compies features from shapefiles into new gdbs
                if fc.endswith("glga"):
                    arcpy.FeatureToLine_management(Component_Map_Folders_Location + "/" + newcode + "_" + maptype + "_" + fc + ".shp", Component_Map_Folders_Location + "/" + newcode + "_" + maptype + "_" + fc + "1.shp", "","ATTRIBUTES")
                    arcpy.Append_management(Component_Map_Folders_Location + "/" + newcode + "_" + maptype + "_" + fc + "1.shp", NewGDB + '/' + newfd + fc[4:], "NO_TEST")
                    arcpy.Delete_management(Component_Map_Folders_Location + '/' + newcode + "_" + maptype + "_" + fc + ".shp")
                    arcpy.Delete_management(Component_Map_Folders_Location + '/' + newcode + "_" + maptype + "_" + fc + "1.shp")
                else:
                    arcpy.Append_management(Component_Map_Folders_Location + '/' + newcode + "_" + maptype + "_" + fc + ".shp", NewGDB + '/' + newfd + fc[4:], "NO_TEST")
                    arcpy.Delete_management(Component_Map_Folders_Location + "/" + newcode + "_" + maptype + "_" + fc + ".shp")
                arcpy.Delete_management(fc + "_lyr")
            else:
                arcpy.SelectLayerByAttribute_management(fc + "_lyr", "CLEAR_SELECTION")
                arcpy.Delete_management(fc + "_lyr")

#------------------------# Fixes attribution of boundary "overshoots"--------------------------------#

for item in fourcodelist:
    string = str(item)
    newcode = re.sub('[(),]', '', string)
    newcode = newcode.lower()
    if "bedrock" in newcode:
        maptype = "bedrock_geology"
    elif "surficial" in newcode:
        maptype = "surficial_geology"
    elif "glacial" in newcode:
        maptype = "glacial_geology"
    elif "geomorphology" in newcode:
        maptype = "geomorphology"
    elif "geohazard" in newcode:
        maptype = "geohazard"
    elif "benthic" in newcode:
        maptype = "benthic_habitat"
    else:
        maptype = "geology"
    if "_" in newcode:
        newcode = newcode.rsplit('_',1)[0]
        newfd = newcode
    else:
        newfd = newcode

    NewGDB = Component_Map_Folders_Location + '/' + newcode + "_" + maptype + ".gdb"
    arcpy.env.workspace = NewGDB
    fds = arcpy.ListDatasets("*", "Feature")
    for fd in fds:
        fcname = fd + MainFC
        arcpy.env.workspace = fd
        fcs = arcpy.ListFeatureClasses()
        for fc in fcs:
            if arcpy.Exists(fc + "a"):
                if int(arcpy.GetCount_management(fc + "a").getOutput(0)) > 0:
                    arcpy.MakeFeatureLayer_management(fc + "a", fc + "layer")
                    arcpy.Dissolve_management(fc + "layer", fc + "dissolve", ["FSUBTYPE", "POS", "NOTES", "SYM", "GMAP_ID"], "", "SINGLE_PART", "DISSOLVE_LINES")
                    arcpy.FeatureToLine_management(fc + "dissolve", fc + "feat2l", "", "ATTRIBUTES")
                    arcpy.DeleteFeatures_management(fc + "layer")
                    arcpy.Append_management(fc + "feat2l", fc + "a", "NO_TEST")
                    arcpy.Delete_management(fc + "feat2l")
                    arcpy.Delete_management(fc + "dissolve")
                    arcpy.Delete_management(fc + "layer")

#-------------------------Fixes ObjectIds & Deletes Empty Feature Classes------------------------------------------------#

    arcpy.Rename_management(NewGDB, Component_Map_Folders_Location + '/' + newcode + "_" + maptype + "_old.gdb")
    arcpy.CreateFileGDB_management(Component_Map_Folders_Location, newcode + "_" + maptype + ".gdb", "CURRENT")
    arcpy.ImportXMLWorkspaceDocument_management(NewGDB, Component_Map_Folders_Location + "\\schema.xml", "SCHEMA_ONLY")
    arcpy.Rename_management(Component_Map_Folders_Location + '/' + newcode + "_" + maptype + ".gdb" + "/" + compfd, Component_Map_Folders_Location + '/' + newcode + "_" + maptype + ".gdb" + "/" + newfd) # Renames FDs in each component map

    arcpy.env.workspace = Component_Map_Folders_Location + '/' + newcode + "_" + maptype + "_old.gdb"
    fds = arcpy.ListDatasets("*", "Feature")
    for fd in fds:
        arcpy.env.workspace = fd
        fcs = arcpy.ListFeatureClasses()
        for fc in fcs:
            arcpy.CopyFeatures_management(fc, Component_Map_Folders_Location + '/' + newcode + "_" + maptype + ".gdb" + "/" + newfd + "/" + fc)
    arcpy.Delete_management(Component_Map_Folders_Location + '/' + newcode + "_" + maptype + "_old.gdb")

for item in fourcodelist:
    string = str(item)
    newcode = re.sub('[(),]', '', string)
    newcode = newcode.lower()
    if "bedrock" in newcode:
        maptype = "bedrock_geology"
    elif "surficial" in newcode:
        maptype = "surficial_geology"
    elif "glacial" in newcode:
        maptype = "glacial_geology"
    elif "geomorphology" in newcode:
        maptype = "geomorphology"
    elif "geohazard" in newcode:
        maptype = "geohazard"
    elif "benthic" in newcode:
        maptype = "benthic_habitat"
    else:
        maptype = "geology"
    if "_" in newcode:
        newcode = newcode.rsplit('_',1)[0]
    NewGDB = Component_Map_Folders_Location + '/' + newcode + "_" + maptype + ".gdb"
    arcpy.env.workspace = NewGDB


    tbls = arcpy.ListTables("*", "All")
    for tbl in tbls:
        arcpy.Delete_management(tbl)

    fds = arcpy.ListDatasets("*", "Feature")
    for fd in fds:
        arcpy.env.workspace = fd
        fcs = arcpy.ListFeatureClasses()
        for fc in fcs:
            #------------Attempts to set Label field to Null of features that have "" in their label field---------#
            arcpy.MakeFeatureLayer_management(fc, fc + "_lyr","", "","")
            arcpy.CalculateField_management(fc + "_lyr", "FUID", "!OBJECTID!", "PYTHON_9.3")
            field_names = [f.name for f in arcpy.ListFields(fc)]
            if "LBL" in field_names:
                arcpy.SelectLayerByAttribute_management(fc + "_lyr", "NEW_SELECTION", select)
                arcpy.CalculateField_management(fc + "_lyr", "LBL", expression1, "PYTHON", codeblock1)
            arcpy.Delete_management(fc +"_lyr")

            #------------Deletes Empty FCs------#
            count = str(arcpy.GetCount_management(fc))
            if count == "0":
                fcAlias = arcpy.Describe(fc).aliasName
                fcType = fc[4:]
                fcsNew = arcpy.ListFeatureClasses()
                for fcNew in fcsNew:
                    oldfcAlias = arcpy.Describe(fcNew).aliasName
                    if str(oldfcAlias) == "":
                        if fcNew[4:] == fcType:
                            arcpy.AlterAliasName(fcNew, fcAlias)
                arcpy.Delete_management(fc)

    arcpy.env.workspace = NewGDB
    fds = arcpy.ListDatasets("*", "Feature")
    for fd in fds:
        arcpy.env.workspace = fd
        fcs = arcpy.ListFeatureClasses()
        for fc in fcs:
            if fc.endswith("gsl"):
                arcpy.AddMessage("CHECK THE SUBTYPES IN " + fc +  " FOR POTENTIAL ERRORS")
            elif "cn" in fc:
                arcpy.AddMessage("CHECK THE SUBTYPES IN " + fc +  " FOR POTENTIAL ERRORS")
            elif fc.endswith("gml"):
                arcpy.AddMessage("CHECK THE SUBTYPES IN " + fc +  " FOR POTENTIAL ERRORS")
            elif fc.endswith("atd"):
                arcpy.AddMessage("CHECK THE SUBTYPES IN " + fc +  " FOR POTENTIAL ERRORS")




 #-----Atempts to copy tables to component map gdbs---------#
    arcpy.env.workspace = WorkingCompGDB
    tbls = arcpy.ListTables("*", "All")
    for tbl in tbls:
        arcpy.Copy_management(tbl, NewGDB + '/' + tbl)

arcpy.env.workspace = Component_Map_Folders_Location
arcpy.Delete_management(Component_Map_Folders_Location + '\\' + "schema.xml")


#-------------------------Adds Topology to Component Map GDBs--------------------------------------#

##    arcpy.env.workspace = NewGDB
##    GP = arcgisscripting.create()
##    try:
##        from topology import * # topology92.py file must be in the same directory as this script
##    except:
##        arcpy.AddMessage("Unable to add topology")
##
##    AddTopology(GP, NewGDB)


