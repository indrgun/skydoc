# Copyright 2016 The Bazel Authors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import os
import tempfile
import textwrap
import unittest
from google.protobuf import text_format
from skydoc import macro_extractor
from src.main.protobuf import build_pb2


class MacroExtractorTest(unittest.TestCase):

  def check_protos(self, src, expected):
    with tempfile.NamedTemporaryFile() as tf:
      tf.write(src)
      tf.flush()

      expected_proto = build_pb2.BuildLanguage()
      text_format.Merge(expected, expected_proto)

      extractor = macro_extractor.MacroDocExtractor()
      extractor.parse_bzl(tf.name)
      proto = extractor.proto()
      self.assertEqual(expected_proto, proto)

  def test_multi_line_description(self):
    src = textwrap.dedent("""\
        def multiline(name, foo=False, visibility=None):
          \"\"\"A rule with multiline documentation.

          Some more documentation about this rule here.

          Args:
            name: A unique name for this rule.
            foo: A test argument.

              Documentation for foo continued here.
            visibility: The visibility of this rule.

              Documentation for visibility continued here.
          \"\"\"
          native.genrule(
              name = name,
              out = ["foo"],
              cmd = "touch $@",
              visibility = visibility,
          )
        """)

    expected = textwrap.dedent("""\
        rule {
          name: "multiline"
          documentation: "A rule with multiline documentation.\\n\\nSome more documentation about this rule here."
          attribute {
            name: "name"
            type: UNKNOWN
            mandatory: true
            documentation: "A unique name for this rule."
          }
          attribute {
            name: "foo"
            type: UNKNOWN
            mandatory: false
            documentation: "A test argument.\\n\\nDocumentation for foo continued here."
          }
          attribute {
            name: "visibility"
            type: UNKNOWN
            mandatory: false
            documentation: "The visibility of this rule.\\n\\nDocumentation for visibility continued here."
          }
        }
        """)

    self.check_protos(src, expected)

  def test_undocumented(self):
    src = textwrap.dedent("""\
        def undocumented(name, visibility=None):
          native.genrule(
              name = name,
              out = ["foo"],
              cmd = "touch $@",
              visibility = visibility,
          )
        """)

    expected = textwrap.dedent("""\
        rule {
          name: "undocumented"
          attribute {
            name: "name"
            type: UNKNOWN
            mandatory: true
          }
          attribute {
            name: "visibility"
            type: UNKNOWN
            mandatory: false
          }
        }
        """)

    self.check_protos(src, expected)

  def test_private_macros_skipped(self):
    src = textwrap.dedent("""\
        def _private(name, visibility=None):
          \"\"\"A private macro that should not appear in docs.

          Args:
            name: A unique name for this rule.
            visibility: The visibility of this rule.
          \"\"\"
          native.genrule(
              name = name,
              out = ["foo"],
              cmd = "touch $@",
              visibility = visibility,
          )

        def public(name, visibility=None):
          \"\"\"A public macro that should appear in docs.

          Args:
            name: A unique name for this rule.
            visibility: The visibility of this rule.
          \"\"\"
          native.genrule(
              name = name,
              out = ["foo"],
              cmd = "touch $@",
              visibility = visibility,
          )
        """)

    expected = textwrap.dedent("""\
        rule {
          name: "public"
          documentation: "A public macro that should appear in docs."
          attribute {
            name: "name"
            type: UNKNOWN
            mandatory: true
            documentation: "A unique name for this rule."
          }
          attribute {
            name: "visibility"
            type: UNKNOWN
            mandatory: false
            documentation: "The visibility of this rule."
          }
        }
        """)

    self.check_protos(src, expected)

  def test_rule_macro_mix(self):
    src = textwrap.dedent("""\
        def _impl(ctx):
          return struct()

        example_rule = rule(
            implementation = _impl,
            attrs = {
                "arg_label": attr.label(),
                "arg_string": attr.string(),
            },
        )
        \"\"\"An example rule.

        Args:
          name: A unique name for this rule.
          arg_label: A label argument.
          arg_string: A string argument.
        \"\"\"

        def example_macro(name, foo, visibility=None):
          \"\"\"An example macro.

          Args:
            name: A unique name for this rule.
            foo: A test argument.
            visibility: The visibility of this rule.
          \"\"\"
          native.genrule(
              name = name,
              out = ["foo"],
              cmd = "touch $@",
              visibility = visibility,
          )
        """)

    expected = textwrap.dedent("""\
        rule {
          name: "example_macro"
          documentation: "An example macro."
          attribute {
            name: "name"
            type: UNKNOWN
            mandatory: true
            documentation: "A unique name for this rule."
          }
          attribute {
            name: "foo"
            type: UNKNOWN
            mandatory: true
            documentation: "A test argument."
          }
          attribute {
            name: "visibility"
            type: UNKNOWN
            mandatory: false
            documentation: "The visibility of this rule."
          }
        }
        """)

    self.check_protos(src, expected)

  def test_file_doc_title_only(self):
    src = textwrap.dedent("""\
        \"\"\"Example rules\"\"\"
        """)
    with tempfile.NamedTemporaryFile() as tf:
      tf.write(src)
      tf.flush()

      extractor = macro_extractor.MacroDocExtractor()
      extractor.parse_bzl(tf.name)
      self.assertEqual('Example rules', extractor.title)
      self.assertEqual('', extractor.description)

  def test_file_doc_title_description(self):
    src = textwrap.dedent("""\
        \"\"\"Example rules

        This file contains example Bazel rules.

        Documentation continued here.
        \"\"\"
        """)
    with tempfile.NamedTemporaryFile() as tf:
      tf.write(src)
      tf.flush()

      extractor = macro_extractor.MacroDocExtractor()
      extractor.parse_bzl(tf.name)
      self.assertEqual('Example rules', extractor.title)
      self.assertEqual('This file contains example Bazel rules.'
                       '\n\nDocumentation continued here.',
                       extractor.description)

  def test_file_doc_title_multiline(self):
    src = textwrap.dedent("""\
        \"\"\"Example rules
        for Bazel

        This file contains example Bazel rules.

        Documentation continued here.
        \"\"\"
        """)
    with tempfile.NamedTemporaryFile() as tf:
      tf.write(src)
      tf.flush()

      extractor = macro_extractor.MacroDocExtractor()
      extractor.parse_bzl(tf.name)
      self.assertEqual('Example rules for Bazel', extractor.title)
      self.assertEqual('This file contains example Bazel rules.'
                       '\n\nDocumentation continued here.',
                       extractor.description)

if __name__ == '__main__':
  unittest.main()