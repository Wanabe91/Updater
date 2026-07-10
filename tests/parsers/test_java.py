from __future__ import annotations

from pathlib import Path

from app.parsers.java import JavaParser


def _parse_file(tmp_path: Path, filename: str, content: str):
    file_path = tmp_path / filename
    file_path.write_text(content, encoding="utf-8")
    return JavaParser().parse(file_path)


class TestPomXml:
    def test_dependencies(self, tmp_path: Path) -> None:
        content = """\
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <dependencies>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-core</artifactId>
      <version>5.3.20</version>
    </dependency>
    <dependency>
      <groupId>junit</groupId>
      <artifactId>junit</artifactId>
      <version>4.13.2</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
"""
        result = _parse_file(tmp_path, "pom.xml", content)
        assert len(result.dependencies) == 2
        spring = next(d for d in result.dependencies if "spring-core" in d.name)
        assert spring.version == "5.3.20"
        assert spring.is_dev is False
        junit = next(d for d in result.dependencies if "junit" in d.name)
        assert junit.is_dev is True

    def test_property_resolution(self, tmp_path: Path) -> None:
        content = """\
<?xml version="1.0" encoding="UTF-8"?>
<project>
  <properties>
    <spring.version>5.3.20</spring.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-core</artifactId>
      <version>${spring.version}</version>
    </dependency>
  </dependencies>
</project>
"""
        result = _parse_file(tmp_path, "pom.xml", content)
        assert len(result.dependencies) == 1
        assert result.dependencies[0].version == "5.3.20"

    def test_provided_scope(self, tmp_path: Path) -> None:
        content = """\
<?xml version="1.0" encoding="UTF-8"?>
<project>
  <dependencies>
    <dependency>
      <groupId>javax.servlet</groupId>
      <artifactId>javax.servlet-api</artifactId>
      <version>4.0.1</version>
      <scope>provided</scope>
    </dependency>
  </dependencies>
</project>
"""
        result = _parse_file(tmp_path, "pom.xml", content)
        assert result.dependencies[0].is_dev is True

    def test_name_format(self, tmp_path: Path) -> None:
        content = """\
<?xml version="1.0" encoding="UTF-8"?>
<project>
  <dependencies>
    <dependency>
      <groupId>com.google.guava</groupId>
      <artifactId>guava</artifactId>
      <version>31.1-jre</version>
    </dependency>
  </dependencies>
</project>
"""
        result = _parse_file(tmp_path, "pom.xml", content)
        assert result.dependencies[0].name == "com.google.guava:guava"

    def test_namespace_handling(self, tmp_path: Path) -> None:
        content = """\
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dependencies>
    <dependency>
      <groupId>org.apache.commons</groupId>
      <artifactId>commons-lang3</artifactId>
      <version>3.12.0</version>
    </dependency>
  </dependencies>
</project>
"""
        result = _parse_file(tmp_path, "pom.xml", content)
        assert len(result.dependencies) == 1

    def test_empty_project(self, tmp_path: Path) -> None:
        content = """\
<?xml version="1.0" encoding="UTF-8"?>
<project></project>
"""
        result = _parse_file(tmp_path, "pom.xml", content)
        assert len(result.dependencies) == 0


class TestBuildGradle:
    def test_string_dependencies(self, tmp_path: Path) -> None:
        content = """\
dependencies {
    implementation 'org.springframework:spring-core:5.3.20'
    testImplementation 'junit:junit:4.13.2'
}
"""
        result = _parse_file(tmp_path, "build.gradle", content)
        assert len(result.dependencies) == 2
        spring = next(d for d in result.dependencies if "spring-core" in d.name)
        assert spring.name == "org.springframework:spring-core"
        assert spring.version == "5.3.20"
        assert spring.is_dev is False
        junit = next(d for d in result.dependencies if "junit" in d.name)
        assert junit.is_dev is True

    def test_kotlin_dsl(self, tmp_path: Path) -> None:
        content = """\
dependencies {
    implementation("org.springframework:spring-core:5.3.20")
    testImplementation("junit:junit:4.13.2")
}
"""
        result = _parse_file(tmp_path, "build.gradle.kts", content)
        assert len(result.dependencies) == 2
        assert result.dependencies[1].is_dev is True

    def test_map_form_groovy(self, tmp_path: Path) -> None:
        content = """\
dependencies {
    api group: 'com.google.guava', name: 'guava', version: '31.1-jre'
}
"""
        result = _parse_file(tmp_path, "build.gradle", content)
        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "com.google.guava:guava"
        assert result.dependencies[0].version == "31.1-jre"

    def test_map_form_kotlin(self, tmp_path: Path) -> None:
        content = """\
dependencies {
    api(group = "com.google.guava", name = "guava", version = "31.1-jre")
}
"""
        result = _parse_file(tmp_path, "build.gradle.kts", content)
        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "com.google.guava:guava"

    def test_skips_comments(self, tmp_path: Path) -> None:
        content = """\
dependencies {
    // implementation 'old:dep:1.0'
    implementation 'org.springframework:spring-core:5.3.20'
}
"""
        result = _parse_file(tmp_path, "build.gradle", content)
        assert len(result.dependencies) == 1

    def test_classfier_stripped(self, tmp_path: Path) -> None:
        content = """\
dependencies {
    implementation 'org.junit:junit:4.13.2:jdk15'
}
"""
        result = _parse_file(tmp_path, "build.gradle", content)
        assert result.dependencies[0].version == "4.13.2"


class TestCanParse:
    def test_matches_java_files(self) -> None:
        parser = JavaParser()
        for name in ("pom.xml", "build.gradle", "build.gradle.kts"):
            assert parser.can_parse(Path(name))

    def test_rejects_other_files(self) -> None:
        parser = JavaParser()
        assert not parser.can_parse(Path("Cargo.toml"))
        assert not parser.can_parse(Path("package.json"))
