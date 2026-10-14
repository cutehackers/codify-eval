import 'package:flutter/foundation.dart';

class Note {
  final int id;
  final String title;
  Note(this.id, this.title);
}

class NoteController extends ChangeNotifier {
  final List<Note> notes = [];
  int nextId = 1;
  void save(String title, {int? id}) {
    final clean = title.trim();
    if (clean.isEmpty) return;
    if (id == null) {
      notes.add(Note(nextId++, clean));
    } else {
      final index = notes.indexWhere((n) => n.id == id);
      if (index < 0) return;
      notes[index] = Note(id, clean);
    }
    notifyListeners();
  }
}
