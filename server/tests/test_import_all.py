def test_import_all():  # noqa: C901
    """Test that all modules in agent_platform.server can be imported without errors."""
    import importlib
    from pathlib import Path

    import agent_platform.core
    import agent_platform.server

    def find_python_modules(directory: Path, package_name: str = "") -> list[str]:
        """Recursively find all Python modules in a directory."""
        modules = []

        for item in directory.iterdir():
            if item.is_file() and item.suffix == ".py":
                # Convert file path to module name
                module_name = item.stem
                if package_name:
                    full_module_name = f"{package_name}.{module_name}"
                else:
                    full_module_name = module_name
                modules.append(full_module_name)
            elif item.is_dir() and (item / "__init__.py").exists():
                # Recursively search subdirectories
                sub_package_name = item.name
                if package_name:
                    sub_package_name = f"{package_name}.{sub_package_name}"
                modules.extend(find_python_modules(item, sub_package_name))

        return modules

    server_base_dir = Path(agent_platform.server.__file__).parent
    server_modules = []
    server_modules.extend(find_python_modules(server_base_dir, "agent_platform.server"))
    for module_name in server_modules:
        # print(f"Server module: {module_name}")
        importlib.import_module(module_name)

    core_base_dir = Path(agent_platform.core.__file__).parent
    core_modules = []
    core_modules.extend(find_python_modules(core_base_dir, "agent_platform.core"))
    for module_name in core_modules:
        # print(f"Core module: {module_name}")
        importlib.import_module(module_name)

    all_modules = set(server_modules + core_modules)

    # Report results
    # print(f"Successfully imported {len(all_modules)} modules")

    assert len(all_modules) > 400, (
        f"Expected to import at least 400 modules, but only imported {len(all_modules)}"
    )
    critical_modules = [
        "agent_platform.server.app",
        "agent_platform.server.main",
        "agent_platform.server.server",
        "agent_platform.server.storage.base",
        "agent_platform.server.kernel.kernel",
    ]

    for critical_module in critical_modules:
        assert critical_module in all_modules, f"Critical module {critical_module} was not imported"

    # Now check that we can import the `banned-module-level-imports` modules from pyproject.toml
    import tomllib

    # Find the pyproject.toml file (based on server_base_dir)
    check_dir = server_base_dir
    while True:
        if check_dir.name == "server":
            check_dir = check_dir.parent
            continue  # We want the one in the top-level directory

        if (check_dir / "pyproject.toml").exists():
            break

        check_dir = check_dir.parent
        if check_dir == check_dir.parent or not check_dir:
            raise ValueError("Could not find pyproject.toml")

    with open(check_dir / "pyproject.toml", "rb") as f:
        toml_config = tomllib.load(f)

    banned_modules = toml_config["tool"]["ruff"]["lint"]["flake8-tidy-imports"][
        "banned-module-level-imports"
    ]
    for banned_module in banned_modules:
        # print(f"Importing module banned from top-level imports: {banned_module}")
        importlib.import_module(banned_module)
