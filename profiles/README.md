# Profiles

`project-robots init` writes one JSON profile here per absolute project path.
The filename includes a path hash, so projects with the same directory name do
not collide.

Profiles define:

- small `readFirst` lists;
- path-based ownership routes;
- project invariants;
- named check commands;
- output and context limits.

Use `example.json` as the schema reference. Generated project profiles are
intended to be reviewed and kept compact.
