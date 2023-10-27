# gramps-fake-tree

A script to generate an example family tree database for Gramps using random data.

**Work in progress.**

## Optional: generate random face images

This uses the service thispersondoesnotexist.com.

```bash
python generate_faces.py N
```

where N is the number of faces to generate (it will generate N colored and N grayscale photos).



## Generate the tree

Usage:

```bash
python fake_tree.py
```

This will create a file `random_tree.gramps`. If images exist in the path, they will be used for people.
