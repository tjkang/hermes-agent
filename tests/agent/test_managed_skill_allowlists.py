"""Behavior contract for prefix-scoped managed skill allowlists."""

import json


def _write_skill(root, name):
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Test skill {name}\n---\n\n# {name}\n",
        encoding="utf-8",
    )


def test_managed_prefix_allowlist_closes_every_skill_loader_surface(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    local_skills = hermes_home / "skills"
    external_skills = tmp_path / "external-skills"
    local_skills.mkdir(parents=True)
    external_skills.mkdir()

    _write_skill(local_skills, "content-factory-dispatch")
    _write_skill(external_skills, "content-factory-produce")
    _write_skill(external_skills, "content-factory-canary")
    (hermes_home / "config.yaml").write_text(
        "skills:\n"
        f"  external_dirs: [{external_skills}]\n"
        "  managed_allowlists:\n"
        "    content-factory-: [content-factory-dispatch]\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    import agent.prompt_builder as prompt_builder
    import agent.skill_commands as skill_commands
    import agent.skill_utils as skill_utils
    import tools.skills_tool as skills_tool

    monkeypatch.setattr(skills_tool, "SKILLS_DIR", local_skills)
    skill_utils._external_dirs_cache_clear()
    skills_tool._SKILLS_CACHE.clear()
    prompt_builder.clear_skills_system_prompt_cache(clear_snapshot=True)
    skill_commands._skill_commands = {}

    names = {entry["name"] for entry in skills_tool._find_all_skills()}
    commands = skill_commands.scan_skill_commands()
    prompt = prompt_builder.build_skills_system_prompt()
    allowed = json.loads(skills_tool.skill_view("content-factory-dispatch"))
    wrong_role = json.loads(skills_tool.skill_view("content-factory-produce"))
    canary = json.loads(skills_tool.skill_view("content-factory-canary"))
    qualified_canary = json.loads(skills_tool.skill_view("plugin:content-factory-canary"))

    assert names == {"content-factory-dispatch"}
    assert set(commands) == {"/content-factory-dispatch"}
    assert "content-factory-dispatch" in prompt
    assert "content-factory-produce" not in prompt
    assert "content-factory-canary" not in prompt
    assert allowed["success"] is True
    assert wrong_role["success"] is False
    assert "managed allowlist" in wrong_role["error"].lower()
    assert canary["success"] is False
    assert "managed allowlist" in canary["error"].lower()
    assert qualified_canary["success"] is False
    assert "managed allowlist" in qualified_canary["error"].lower()


def test_duplicate_allowed_managed_name_fails_closed_on_every_surface(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    local_skills = hermes_home / "skills"
    external_skills = tmp_path / "external-skills"
    local_skills.mkdir(parents=True)
    external_skills.mkdir()
    _write_skill(local_skills, "content-factory-dispatch")
    _write_skill(external_skills, "content-factory-dispatch")
    (hermes_home / "config.yaml").write_text(
        "skills:\n"
        f"  external_dirs: [{external_skills}]\n"
        "  managed_allowlists:\n"
        "    content-factory-: [content-factory-dispatch]\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    import agent.prompt_builder as prompt_builder
    import agent.skill_commands as skill_commands
    import agent.skill_utils as skill_utils
    import tools.skills_tool as skills_tool

    monkeypatch.setattr(skills_tool, "SKILLS_DIR", local_skills)
    skill_utils._external_dirs_cache_clear()
    skills_tool._SKILLS_CACHE.clear()
    prompt_builder.clear_skills_system_prompt_cache(clear_snapshot=True)
    skill_commands._skill_commands = {}

    names = {entry["name"] for entry in skills_tool._find_all_skills()}
    commands = skill_commands.scan_skill_commands()
    prompt = prompt_builder.build_skills_system_prompt()
    viewed = json.loads(skills_tool.skill_view("content-factory-dispatch"))

    assert "content-factory-dispatch" not in names
    assert "/content-factory-dispatch" not in commands
    assert "content-factory-dispatch" not in prompt
    assert viewed["success"] is False
    assert "ambiguous" in viewed["error"].lower()


def test_skill_command_cache_refreshes_when_managed_policy_changes(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    local_skills = hermes_home / "skills"
    local_skills.mkdir(parents=True)
    _write_skill(local_skills, "content-factory-dispatch")
    config_path = hermes_home / "config.yaml"
    config_path.write_text(
        "skills:\n  managed_allowlists:\n"
        "    content-factory-: [content-factory-dispatch]\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    import agent.skill_commands as skill_commands
    import agent.skill_utils as skill_utils
    import tools.skills_tool as skills_tool

    monkeypatch.setattr(skills_tool, "SKILLS_DIR", local_skills)
    skill_utils._external_dirs_cache_clear()
    skill_commands._skill_commands = {}
    skill_commands._skill_commands_platform = None
    assert "/content-factory-dispatch" in skill_commands.get_skill_commands()

    config_path.write_text(
        "skills:\n  managed_allowlists:\n    content-factory-: []\n",
        encoding="utf-8",
    )
    assert "/content-factory-dispatch" not in skill_commands.get_skill_commands()


def test_malformed_managed_allowlist_value_fails_closed_without_crashing(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    local_skills = hermes_home / "skills"
    local_skills.mkdir(parents=True)
    _write_skill(local_skills, "content-factory-dispatch")
    (hermes_home / "config.yaml").write_text(
        "skills:\n  managed_allowlists:\n    content-factory-: 42\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    import agent.skill_utils as skill_utils
    import tools.skills_tool as skills_tool

    monkeypatch.setattr(skills_tool, "SKILLS_DIR", local_skills)
    skill_utils._external_dirs_cache_clear()
    skills_tool._SKILLS_CACHE.clear()

    assert skill_utils.get_managed_skill_allowlists() == {"content-factory-": frozenset()}
    assert skills_tool._find_all_skills() == []


def test_reserved_directory_cannot_escape_policy_with_harmless_frontmatter_alias(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    local_skills = hermes_home / "skills"
    alias_dir = local_skills / "content-factory-canary"
    alias_dir.mkdir(parents=True)
    (alias_dir / "SKILL.md").write_text(
        "---\nname: harmless-alias\ndescription: Must remain hidden\n---\n",
        encoding="utf-8",
    )
    (hermes_home / "config.yaml").write_text(
        "skills:\n  managed_allowlists:\n"
        "    content-factory-: [content-factory-dispatch]\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    import agent.prompt_builder as prompt_builder
    import agent.skill_commands as skill_commands
    import agent.skill_utils as skill_utils
    import tools.skills_tool as skills_tool

    monkeypatch.setattr(skills_tool, "SKILLS_DIR", local_skills)
    skill_utils._external_dirs_cache_clear()
    skills_tool._SKILLS_CACHE.clear()
    prompt_builder.clear_skills_system_prompt_cache(clear_snapshot=True)
    skill_commands._skill_commands = {}

    assert skills_tool._find_all_skills() == []
    assert "/harmless-alias" not in skill_commands.scan_skill_commands()
    assert "harmless-alias" not in prompt_builder.build_skills_system_prompt()
    viewed = json.loads(skills_tool.skill_view("harmless-alias"))
    assert viewed["success"] is False
    assert "managed allowlist" in viewed["error"].lower()


def test_source_bound_managed_skill_cannot_fall_back_to_external_dir(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    local_skills = hermes_home / "skills"
    external_skills = tmp_path / "external-skills"
    local_skills.mkdir(parents=True)
    external_skills.mkdir()
    _write_skill(local_skills, "content-factory-dispatch")
    expected_source = local_skills / "content-factory-dispatch" / "SKILL.md"
    (hermes_home / "config.yaml").write_text(
        "skills:\n"
        f"  external_dirs: [{external_skills}]\n"
        "  managed_allowlists:\n"
        "    content-factory-:\n"
        f"      content-factory-dispatch: {expected_source}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    import agent.prompt_builder as prompt_builder
    import agent.skill_commands as skill_commands
    import agent.skill_utils as skill_utils
    import tools.skills_tool as skills_tool

    monkeypatch.setattr(skills_tool, "SKILLS_DIR", local_skills)
    skill_utils._external_dirs_cache_clear()
    skills_tool._SKILLS_CACHE.clear()
    prompt_builder.clear_skills_system_prompt_cache(clear_snapshot=True)
    skill_commands._skill_commands = {}

    assert {entry["name"] for entry in skills_tool._find_all_skills()} == {
        "content-factory-dispatch"
    }
    assert "/content-factory-dispatch" in skill_commands.scan_skill_commands()
    assert "content-factory-dispatch" in prompt_builder.build_skills_system_prompt()
    assert json.loads(skills_tool.skill_view("content-factory-dispatch"))["success"] is True

    expected_source.parent.rename(external_skills / "content-factory-dispatch")
    skill_utils._external_dirs_cache_clear()
    skills_tool._SKILLS_CACHE.clear()
    prompt_builder.clear_skills_system_prompt_cache(clear_snapshot=True)
    skill_commands._skill_commands = {}

    assert skills_tool._find_all_skills() == []
    assert "/content-factory-dispatch" not in skill_commands.scan_skill_commands()
    assert "content-factory-dispatch" not in prompt_builder.build_skills_system_prompt()
    viewed = json.loads(skills_tool.skill_view("content-factory-dispatch"))
    assert viewed["success"] is False
    assert "managed allowlist" in viewed["error"].lower()


def test_prompt_cache_refreshes_when_managed_source_binding_changes(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    local_skills = hermes_home / "skills"
    local_skills.mkdir(parents=True)
    _write_skill(local_skills, "content-factory-dispatch")
    local_source = local_skills / "content-factory-dispatch" / "SKILL.md"
    other_source = tmp_path / "elsewhere" / "content-factory-dispatch" / "SKILL.md"
    config_path = hermes_home / "config.yaml"
    config_path.write_text(
        "skills:\n  managed_allowlists:\n    content-factory-:\n"
        f"      content-factory-dispatch: {local_source}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    import agent.prompt_builder as prompt_builder
    import agent.skill_utils as skill_utils

    skill_utils._external_dirs_cache_clear()
    prompt_builder.clear_skills_system_prompt_cache(clear_snapshot=True)
    assert "content-factory-dispatch" in prompt_builder.build_skills_system_prompt()

    config_path.write_text(
        "skills:\n  managed_allowlists:\n    content-factory-:\n"
        f"      content-factory-dispatch: {other_source}\n",
        encoding="utf-8",
    )
    assert "content-factory-dispatch" not in prompt_builder.build_skills_system_prompt()


def test_legacy_prompt_snapshot_without_source_path_is_invalidated(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    local_skills = hermes_home / "skills"
    local_skills.mkdir(parents=True)
    _write_skill(local_skills, "content-factory-dispatch")
    local_source = local_skills / "content-factory-dispatch" / "SKILL.md"
    (hermes_home / "config.yaml").write_text(
        "skills:\n  managed_allowlists:\n    content-factory-:\n"
        f"      content-factory-dispatch: {local_source}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    import agent.prompt_builder as prompt_builder
    import agent.skill_utils as skill_utils

    skill_utils._external_dirs_cache_clear()
    prompt_builder.clear_skills_system_prompt_cache(clear_snapshot=True)
    assert "content-factory-dispatch" in prompt_builder.build_skills_system_prompt()

    snapshot_path = hermes_home / ".skills_prompt_snapshot.json"
    legacy = json.loads(snapshot_path.read_text(encoding="utf-8"))
    legacy["version"] = 1
    for entry in legacy["skills"]:
        entry.pop("source_path", None)
    snapshot_path.write_text(json.dumps(legacy), encoding="utf-8")
    prompt_builder.clear_skills_system_prompt_cache()

    assert "content-factory-dispatch" in prompt_builder.build_skills_system_prompt()
    refreshed = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert refreshed["version"] > 1
    assert all(entry.get("source_path") for entry in refreshed["skills"])


def test_malformed_managed_policy_node_blocks_all_skill_loading(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    local_skills = hermes_home / "skills"
    local_skills.mkdir(parents=True)
    _write_skill(local_skills, "ordinary-skill")
    (hermes_home / "config.yaml").write_text(
        "skills:\n  managed_allowlists: 42\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    import agent.skill_utils as skill_utils
    import tools.skills_tool as skills_tool

    monkeypatch.setattr(skills_tool, "SKILLS_DIR", local_skills)
    skill_utils._external_dirs_cache_clear()
    skills_tool._SKILLS_CACHE.clear()

    assert skill_utils.get_managed_skill_allowlists() == {"": frozenset()}
    assert skills_tool._find_all_skills() == []


def test_unreadable_yaml_blocks_all_skill_loading(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    local_skills = hermes_home / "skills"
    local_skills.mkdir(parents=True)
    _write_skill(local_skills, "ordinary-skill")
    (hermes_home / "config.yaml").write_text(
        "skills:\n  managed_allowlists: [\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    import agent.skill_utils as skill_utils
    import tools.skills_tool as skills_tool

    monkeypatch.setattr(skills_tool, "SKILLS_DIR", local_skills)
    skill_utils._external_dirs_cache_clear()
    skills_tool._SKILLS_CACHE.clear()

    assert skill_utils.get_managed_skill_allowlists() == {"": frozenset()}
    assert skills_tool._find_all_skills() == []


def test_managed_plugin_requires_explicit_source_binding(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    local_skills = hermes_home / "skills"
    local_skills.mkdir(parents=True)
    plugin_skill = tmp_path / "plugins" / "canary" / "content-factory-dispatch" / "SKILL.md"
    plugin_skill.parent.mkdir(parents=True)
    plugin_skill.write_text(
        "---\nname: content-factory-dispatch\ndescription: plugin impersonator\n---\n",
        encoding="utf-8",
    )
    config_path = hermes_home / "config.yaml"
    config_path.write_text(
        "skills:\n  managed_allowlists:\n"
        "    content-factory-: [content-factory-dispatch]\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    import agent.skill_utils as skill_utils
    from hermes_cli import plugins as plugins_mod
    from hermes_cli.plugins import PluginManager
    import tools.skills_tool as skills_tool

    manager = PluginManager()
    manager._plugin_skills["canary:content-factory-dispatch"] = {
        "path": plugin_skill,
        "plugin": "canary",
        "bare_name": "content-factory-dispatch",
        "description": "plugin impersonator",
    }
    monkeypatch.setattr(plugins_mod, "_plugin_manager", manager)
    monkeypatch.setattr(skills_tool, "SKILLS_DIR", local_skills)
    skill_utils._external_dirs_cache_clear()
    skills_tool._SKILLS_CACHE.clear()

    blocked = json.loads(skills_tool.skill_view("canary:content-factory-dispatch"))
    assert blocked["success"] is False
    assert "managed allowlist" in blocked["error"].lower()

    config_path.write_text(
        "skills:\n  managed_allowlists:\n    content-factory-:\n"
        f"      content-factory-dispatch: {plugin_skill}\n",
        encoding="utf-8",
    )
    skill_utils._external_dirs_cache_clear()
    skills_tool._SKILLS_CACHE.clear()

    allowed = json.loads(skills_tool.skill_view("canary:content-factory-dispatch"))
    assert allowed["success"] is True
