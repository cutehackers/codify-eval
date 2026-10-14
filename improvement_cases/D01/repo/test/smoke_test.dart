import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

class Immediate implements SearchService {
  @override
  Future<List<String>> search(String query) async => [query];
}

void main() {
  test('successful search remains supported', () async {
    final c = SearchController(Immediate());
    await c.search('tea');
    expect(c.state.phase, SearchPhase.ready);
    expect(c.state.items, ['tea']);
    c.dispose();
  });
}
