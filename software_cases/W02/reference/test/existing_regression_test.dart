import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:todos_app/todo.dart';
import 'package:todos_app/todo_store.dart';
import 'package:todos_app/todo_controller.dart';

void main() {
  test('existing creation completion and file restoration', () async {
    final directory = await Directory.systemTemp.createTemp('existing-todos-');
    addTearDown(() => directory.delete(recursive: true));
    final controller = TodoController(store: TodoStore(directory: directory));
    await controller.initialize();
    expect(controller.loaded, true);
    expect(controller.items, isEmpty);
    await controller.add('   기존 항목   ');
    await controller.add('   ');
    expect(controller.items.length, 1);
    expect(controller.items.single.title, '기존 항목');
    final id = controller.items.single.id;
    await controller.toggle(id);
    expect(controller.items.single.done, true);
    final saved =
        jsonDecode(await File('${directory.path}/todos.json').readAsString())
            as List;
    expect(saved.single['id'], id);
    final restored = TodoController(store: TodoStore(directory: directory));
    await restored.initialize();
    expect(restored.items.single.id, id);
    expect(restored.items.single.title, '기존 항목');
    expect(restored.items.single.done, true);
    await restored.toggle(id);
    expect(restored.items.single.done, false);
    controller.dispose();
    restored.dispose();
  });
  test('existing Todo constructor and serialization', () {
    const item = Todo(id: 'legacy-id', title: '레거시 제목', done: true);
    final copy = Todo.fromJson(item.toJson());
    expect(copy.id, item.id);
    expect(copy.title, item.title);
    expect(copy.done, item.done);
    expect(copy.copyWith(done: false).id, item.id);
    expect(copy.copyWith(done: false).title, item.title);
  });
}
