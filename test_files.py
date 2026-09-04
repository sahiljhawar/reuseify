# SPDX-FileCopyrightText: 2026 GFZ Helmholtz Centre for Geosciences
# SPDX-FileContributor: sahil
#
# SPDX-License-Identifier: Apache-2.0

# write a code to add random py files with random code

import os
import random
import string


def random_code() -> str:
    """Generate random Python code."""
    lines = []
    for _ in range(random.randint(5, 15)):
        var_name = "".join(random.choices(string.ascii_lowercase, k=5))
        value = random.randint(1, 100)
        lines.append(f"{var_name} = {value}")
    return "\n".join(lines)


def create_random_py_files(num_files: int, directory: str) -> None:
    """Create random Python files with random code."""
    os.makedirs(directory, exist_ok=True)
    for i in range(num_files):
        filename = f"random_file_{i}.py"
        filepath = os.path.join(directory, filename)
        with open(filepath, "w") as f:
            f.write(random_code())


if __name__ == "__main__":
    create_random_py_files(10, "./")
