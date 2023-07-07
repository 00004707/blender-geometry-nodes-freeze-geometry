# Freeze Geometry in geometry nodes

![Node Group](https://i.imgur.com/srPO5Ml.png)

"proof-of-concept" script. Currently does not work for anything other than "mesh". 
Might be turned into a true addon with custom node someday.

Install the .py file as an addon.

The cache is an 'Object Info' node, and not a true cache.

What this script does:
* Copy the active object
* Copy the node group on cloned object
* On cloned node group, connect the "Group Output Node" where user wanted the cache
* Apply the node group on clone, creating a "cache object"
* Go back to the original object and original node group.
* Add a Object Info node where cache is supposed to be
* Set it's value to "cache object"
* Connect the new node to the rest

In current state it allowed me to reduce computation times for very complex hair/fur cards generator, that was used on a single mesh.

![comp time](https://i.imgur.com/1ufQDxy.png)