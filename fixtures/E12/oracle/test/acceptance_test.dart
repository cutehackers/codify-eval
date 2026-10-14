import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

void main() {
  testWidgets('create edit recreate', (t) async {
    final controller = NoteController();
    await t.pumpWidget(NoteApp(controller: controller));
    await t.enterText(find.byKey(const Key('title')), '   ');
    await t.tap(find.byKey(const Key('save')));
    await t.pump();
    expect(find.text('기록 없음'), findsOneWidget);
    for (final title in [' 산책 ', '독서']) {
      await t.enterText(find.byKey(const Key('title')), title);
      await t.tap(find.byKey(const Key('save')));
      await t.pump();
    }
    expect(controller.notes.length, 2);
    final id = controller.notes.first.id;
    expect(controller.notes.last.id, isNot(id));
    await t.tap(find.byKey(ValueKey('note-$id')));
    await t.pump();
    await t.enterText(find.byKey(const Key('title')), '긴 산책');
    await t.tap(find.byKey(const Key('save')));
    await t.pump();
    expect(controller.notes.length, 2);
    expect(controller.notes.first.id, id);
    expect(controller.notes.first.title, '긴 산책');
    await t.pumpWidget(const SizedBox());
    await t.pumpWidget(NoteApp(controller: controller));
    expect(find.text('긴 산책'), findsOneWidget);
    expect(find.text('독서'), findsOneWidget);
  });
}
