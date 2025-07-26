from tree_sitter import Language, Parser
import tree_sitter_python as tsp

lang = Language(tsp.language())
parser = Parser(lang)          # ← correct