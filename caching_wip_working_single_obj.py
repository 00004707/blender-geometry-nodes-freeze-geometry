from functools import cache
import bpy
from mathutils import Vector

bl_info = {
    "name": "Geometry nodes cache test",
    "author": "00004707",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "asdf",
    "description": "asdf",
    "doc_url": "",
    "category": "Interface",
}


def get_friendly_node_name(node):
    if node.label != "":
        return node.label
    if node.type == "GROUP":
        return node.node_tree.name
    return node.name

def CheckForGeometryInputOutput(node, outputs = False):
    if outputs:
        for output in node.outputs:
            if output.type == "GEOMETRY":
                return True
        return False
    else:
        for input in node.inputs:
            if output.type == "GEOMETRY":
                return True
        return False


def dynamic_node_outputs_enum(scene, context):

    valid_outputs = []

    node_tree = node = context.space_data.node_tree
    node = node_tree.nodes.active
    for i, output in enumerate(node.outputs):
            if output.type == "GEOMETRY":
                valid_outputs.append((str(i), output.name, f"Cache {output.name} geometry output"))

    return valid_outputs

#class ValidNodeOutputs(PropertyGroup):



class GNGeometryCache(bpy.types.Operator):
    bl_idname = "nodes.geometry_cache"
    bl_label = "Cache Geometry Output"
    bl_description = "Creates a geometry cache at selected node"
    bl_options = {'REGISTER', 'UNDO'} #INTERNAL
    
#    clear: bpy.props.BoolProperty(name="clear", default = False)
#    random: bpy.props.BoolProperty(name="clear", default = False)
#    random_range: bpy.props.BoolProperty(name="clear", default = False)
    
    selected_output : bpy.props.EnumProperty(
        name="Output:",
        description="Select output to cache",
        items=dynamic_node_outputs_enum
        )
    
    pre_modifier_action: bpy.props.EnumProperty(
        name="Pre-modifiers action",
        description="Defines an action for other modifiers in the stack of this object",
        items=[
            ('BYPASS', "Bypass", "Leave modifiers as is (might create unexpected result)"),
            ('REMOVE', "Remove", "Remove modifiers before this geometry nodes setup"),
            ('APPLY', "Apply", "Apply all modifiers in the stack before this geometry nodes setup"),
        ],
        default="APPLY"
    )

    post_modifier_action: bpy.props.EnumProperty(
        name="Post-modifiers action",
        description="Defines an action for other modifiers in the stack of this object",
        items=[
            ('BYPASS', "Bypass", "Leave modifiers as is (might create unexpected result)"),
            ('REMOVE', "Remove", "Remove modifiers after this geometry nodes setup"),
            ('APPLY', "Apply", "Apply all modifiers in the stack after this geometry nodes setup"),
        ],
        default="REMOVE"
    )

    custom_identifier: bpy.props.StringProperty(name="Identifier", description="Custom text for identification of the cache", default = "Cache")
    parent_obj = None
    node = None
    node_tree = None
    multi_output = False
    pre_modifiers = True
    post_modifiers = True ##TEST for THIS

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.space_data.type == "NODE_EDITOR" and 
                context.space_data.node_tree and 
                context.space_data.tree_type == 'GeometryNodeTree' and 
                context.space_data.node_tree.nodes.active and
                CheckForGeometryInputOutput(context.space_data.node_tree.nodes.active, True))
    
    def invoke(self, context, event):
        
        self.parent_obj = context.active_object
        self.node_tree = context.space_data.node_tree
        self.node = self.node_tree.nodes.active
        self.custom_identifier = self.node.label if self.node.label is not "" else self.node.name
        
        # There is already a check if there are any geometry outputs, but single node can have multiple
        # Ask user which one has to be cached

        valid_outputs = []
        for output in self.node.outputs:
            if output.type == "GEOMETRY":
                valid_outputs.append(output)
        
        if len(valid_outputs) > 1:
            self.multi_output = True
        
        return context.window_manager.invoke_props_dialog(self)

            

    def execute(self, context):
        
        gn_objs_to_cache = []
        gn_objs_mod_ids = []

        # get all objects that have the modifier
        gn_compat_obj_types = ['MESH', 'CURVE', 'CURVES', 'VOLUME']
        for object in bpy.data.objects:
            if object.type in gn_compat_obj_types:
                    gn_found = False
                    current_obj_gn_mod_ids = []
                    for i, modifier in enumerate(object.modifiers):
                        # add support for nested node groups here
                        if modifier.type == 'NODES' and modifier.node_group == self.node_tree:
                            gn_found = True
                            if object not in gn_objs_to_cache:
                                gn_objs_to_cache.append(object)
                            current_obj_gn_mod_ids.append(i)
                    if gn_found:
                        gn_objs_mod_ids.append(current_obj_gn_mod_ids)
        #edge case: modifer not applying as the cached output is different type than current obj.

        # Create cache object for each one * modifier cnt
        # Create a node group with object input or instance input with id

        #
        # WARNING FOR MULTIPLE OBJECTS CHANGE PARENT OBJECT REF

        #warn: active object might not have this geometry nodes selected lol

        # Duplicate object, not linked to any scene
        parent_name = self.parent_obj.name
        cache_object = self.parent_obj.copy()
        cache_object.name  = f"{self.custom_identifier}_{parent_name}_GNCACHE"
        cache_object.data = self.parent_obj.data.copy()
        # not sure, but let's clear the anims too
        cache_object.animation_data_clear()
        # add object to collection as usage of bpy.ops on active object will be required
        bpy.context.collection.objects.link(cache_object)
        bpy.context.view_layer.objects.active = cache_object


        # Duplicate modifier
        cached_nodegroup = self.node_tree.copy()
        cached_nodegroup.name = f".GNCACHE_{self.custom_identifier}_{parent_name}"
        
        # Connect node to group output
        
        #Remove all group outputs
        for node in cached_nodegroup.nodes:
            if node.type == "GROUP_OUTPUT":
                cached_nodegroup.nodes.remove(node)

        new_group_output = cached_nodegroup.nodes.new("NodeGroupOutput")
        print(len(cached_nodegroup.nodes[self.node.name].outputs))
        # since "Modifier: "GeometryNodes", Node group's first output must be a geometry" then
        cached_nodegroup.links.new(cached_nodegroup.nodes[self.node.name].outputs[int(self.selected_output)], new_group_output.inputs[0])
        # TODO:NESTED CACHES

        # Find the geometry nodes modifier
        nodes_mod_index = -1
        nodes_mod_name = ""
        for i, modifier in enumerate(cache_object.modifiers):
            if modifier.type == 'NODES' and modifier.node_group == self.node_tree:
                nodes_mod_index = i
                nodes_mod_name = modifier.name
                # break # actually, find the last one
        
        cache_object.modifiers[nodes_mod_index].node_group = cached_nodegroup

        # Apply/discard (toggleable) modifiers BEFORE the gn modifier
        # TODO: or perhaps copy nearest loc for armatures

        # create a name list as the indexes will be changed
        mod_names = [modifier.name for modifier in cache_object.modifiers]
        if not self.pre_modifier_action == "BYPASS":
            for i in range(0, nodes_mod_index):
                if self.pre_modifier_action == "REMOVE":
                    bpy.ops.object.modifier_remove(modifier=mod_names[i])
                elif self.pre_modifier_action == "APPLY":
                    bpy.ops.object.modifier_apply(modifier=mod_names[i])
        
        if not self.post_modifier_action == "BYPASS":
            for i in range(nodes_mod_index+1, len(mod_names)):
                if self.post_modifier_action == "REMOVE":
                    bpy.ops.object.modifier_remove(modifier=mod_names[i])
                elif self.post_modifier_action == "APPLY":
                    bpy.ops.object.modifier_apply(modifier=mod_names[i])

        # Apply the cached node & unlink from collection
        bpy.ops.object.modifier_apply(modifier=nodes_mod_name)
        bpy.context.collection.objects.unlink(cache_object)

        bpy.context.view_layer.objects.active = self.parent_obj

        # Create a cache node on source geometry
        cache_node = self.node_tree.nodes.new("GeometryNodeObjectInfo")
        cache_node.location = self.node.location + Vector((0, 200))
        cache_node.label = f"{self.custom_identifier} Cache"
        cache_node.name = f"{self.custom_identifier} Cache"
        cache_node.use_custom_color = True
        cache_node.color = (0.09, 0.02, 0.23)
        cache_node.width = 250
        cache_node.transform_space = 'ORIGINAL'
        cache_node.inputs[0].default_value = cache_object
        # possible multiple links, link to all
        
        for link in self.node.outputs[int(self.selected_output)].links:
            target_socket = link.to_socket
            self.node_tree.links.remove(link)
            self.node_tree.links.new(cache_node.outputs["Geometry"], target_socket)


        # deselect the node
        self.node.select = False
        
        return {'FINISHED'}            
    
    def draw(self, context):
        row = self.layout
        row.prop(self, "custom_identifier", text="Identifier")
        if self.multi_output:
            row.prop(self, "selected_output", text="Output")
        if self.pre_modifiers or self.post_modifiers:
            row.label(text="Modifiers action")
            if self.pre_modifiers:
                row.prop(self, "pre_modifier_action", text="Pre GN Mod")
            if self.post_modifiers:
                row.prop(self, "post_modifier_action", text="Post GN Mod")
    
def append_menu(self, context):
    if context.space_data.tree_type == 'GeometryNodeTree' and context.space_data.node_tree.nodes.active:
        node = context.space_data.node_tree.nodes.active
        self.layout.operator_context = "INVOKE_DEFAULT"
        self.layout.operator("nodes.geometry_cache", text=f"Cache {get_friendly_node_name(node)} Geometry Output")

classes = [GNGeometryCache]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.NODE_MT_context_menu.append(append_menu)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.NODE_MT_context_menu.remove(append_menu)

if __name__ == "__main__":
    register()
