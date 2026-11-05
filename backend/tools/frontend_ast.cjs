// Parse source only. Never load configuration or execute code from the review checkout.
const fs = require('node:fs');
const ts = require('./parser/node_modules/typescript');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = input.map(({file, source}) => {
  const tree = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
  if (tree.parseDiagnostics.length) throw new Error(`Syntax errors in ${file}`);
  const options = {target: ts.ScriptTarget.Latest, noLib: true, noResolve: true, allowJs: true};
  const host = ts.createCompilerHost(options);
  host.getSourceFile = name => name === file ? tree : undefined;
  host.fileExists = name => name === file;
  host.readFile = name => name === file ? source : undefined;
  const checker = ts.createProgram([file], options, host).getTypeChecker();
  const symbols = [], imports = [], references = new Set();
  function walk(node) {
    if (ts.isImportDeclaration(node) && node.importClause) {
      const bindings = node.importClause.namedBindings;
      if (bindings && ts.isNamedImports(bindings)) {
        for (const item of bindings.elements) imports.push({module: node.moduleSpecifier.text,
          imported: (item.propertyName || item.name).text, local: item.name.text});
      }
      if (node.importClause.name) imports.push({module: node.moduleSpecifier.text,
        imported: 'default', local: node.importClause.name.text});
    }
    if (ts.isIdentifier(node) && !ts.isImportSpecifier(node.parent) &&
        !ts.isImportClause(node.parent)) {
      const binding = checker.getSymbolAtLocation(node);
      if (binding?.declarations?.some(d => ts.isImportSpecifier(d) || ts.isImportClause(d))) {
        references.add(node.text);
      }
    }
    const fn = ts.isFunctionDeclaration(node) ? node :
      ts.isVariableDeclaration(node) && node.initializer &&
      (ts.isArrowFunction(node.initializer) || ts.isFunctionExpression(node.initializer)) ? node.initializer : null;
    if (fn && fn.body) {
      const owner = ts.isVariableDeclaration(node) ? node.parent.parent : node;
      const exported = !!owner.modifiers?.some(m => m.kind === ts.SyntaxKind.ExportKeyword);
      const name = node.name?.getText(tree);
      if (name) {
        const end = tree.getLineAndCharacterOfPosition(fn.body.end).line;
        const bodyStart = fn.body.getStart(tree) + (ts.isBlock(fn.body) ? 1 : 0);
        const bodyEnd = fn.body.end - (ts.isBlock(fn.body) ? 1 : 0);
        const scanner = ts.createScanner(ts.ScriptTarget.Latest, false, ts.LanguageVariant.JSX,
          source.slice(bodyStart, bodyEnd));
        const lines = new Set();
        for (let token = scanner.scan(); token !== ts.SyntaxKind.EndOfFileToken; token = scanner.scan()) {
          if ([ts.SyntaxKind.WhitespaceTrivia, ts.SyntaxKind.NewLineTrivia,
               ts.SyntaxKind.SingleLineCommentTrivia, ts.SyntaxKind.MultiLineCommentTrivia].includes(token)) continue;
          const first = tree.getLineAndCharacterOfPosition(bodyStart + scanner.getTokenPos()).line;
          const last = tree.getLineAndCharacterOfPosition(bodyStart + scanner.getTextPos() - 1).line;
          for (let line = first; line <= last; line++) lines.add(line);
        }
        symbols.push({name, exported, defaultExport: !!owner.modifiers?.some(m => m.kind === ts.SyntaxKind.DefaultKeyword),
          start_line: tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1,
          end_line: end + 1, logic_lines: lines.size,
          params: fn.parameters.map(p => p.name.getText(tree)),
          documented_params: (node.jsDoc || owner.jsDoc || []).flatMap(d =>
            (d.tags || []).filter(t => ts.isJSDocParameterTag(t)).map(t => t.name.getText(tree))),
          source: node.getText(tree)});
      }
    }
    ts.forEachChild(node, walk);
  }
  walk(tree);
  return {file, symbols, imports, references: [...references]};
});
process.stdout.write(JSON.stringify(results));
