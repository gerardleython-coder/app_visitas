import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

abstract final class AppColors {
  static const canvas = Color(0xFF003B5C);
  static const surface = canvas;
  static const forest = Color(0xFFFFFFFF);
  static const forestSoft = Color(0xFF014421);
  static const pine = Color(0xFFD4AF37);
  static const mint = Color(0xFFD4AF37);
  static const text = Color(0xFFFFFFFF);
  static const muted = Color(0xFFFFFFFF);
  static const line = Color(0x66FFFFFF);
  static const soft = canvas;
  static const coral = Color(0xFFD4AF37);
  static const coralSoft = canvas;
  static const gold = Color(0xFFD4AF37);
}

abstract final class AppTheme {
  static ThemeData get light {
    final base = GoogleFonts.manropeTextTheme().apply(
      bodyColor: AppColors.text,
      displayColor: AppColors.text,
    );
    return ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: AppColors.canvas,
      colorScheme: const ColorScheme.dark(
        primary: AppColors.forestSoft,
        onPrimary: AppColors.text,
        secondary: AppColors.pine,
        onSecondary: AppColors.canvas,
        error: AppColors.coral,
        onError: AppColors.canvas,
        surface: AppColors.surface,
        onSurface: AppColors.text,
      ).copyWith(
        primaryContainer: AppColors.forestSoft,
        onPrimaryContainer: AppColors.text,
        secondaryContainer: AppColors.gold,
        onSecondaryContainer: AppColors.canvas,
        onSurfaceVariant: AppColors.text,
        outline: AppColors.line,
        outlineVariant: AppColors.line,
        surfaceContainerLowest: AppColors.surface,
        surfaceContainerLow: AppColors.surface,
        surfaceContainer: AppColors.surface,
        surfaceContainerHigh: AppColors.surface,
        surfaceContainerHighest: AppColors.surface,
      ),
      textTheme: base.copyWith(
        headlineMedium: GoogleFonts.literata(
          fontSize: 24,
          height: 1.2,
          fontWeight: FontWeight.w600,
          color: AppColors.text,
        ),
        headlineSmall: GoogleFonts.literata(
          fontSize: 21,
          height: 1.25,
          fontWeight: FontWeight.w600,
          color: AppColors.text,
        ),
        titleLarge: base.titleLarge?.copyWith(
          color: AppColors.text,
          fontWeight: FontWeight.w700,
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.canvas,
        foregroundColor: AppColors.text,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardTheme(
        color: AppColors.surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
          side: const BorderSide(color: AppColors.line),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: const BorderSide(color: AppColors.line),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: const BorderSide(color: AppColors.line),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: const BorderSide(color: AppColors.gold, width: 1.5),
        ),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        labelStyle: const TextStyle(color: AppColors.text),
        floatingLabelStyle: const TextStyle(color: AppColors.gold),
        hintStyle: const TextStyle(color: AppColors.muted),
        prefixIconColor: AppColors.gold,
        suffixIconColor: AppColors.gold,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.surface,
        indicatorColor: AppColors.gold,
        iconTheme: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return IconThemeData(
            color: selected ? AppColors.canvas : AppColors.text,
          );
        }),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return base.labelSmall?.copyWith(
            color: selected ? AppColors.text : AppColors.muted,
            fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
          );
        }),
      ),
      navigationRailTheme: const NavigationRailThemeData(
        backgroundColor: AppColors.surface,
        indicatorColor: AppColors.gold,
        selectedIconTheme: IconThemeData(color: AppColors.canvas),
        unselectedIconTheme: IconThemeData(color: AppColors.text),
        selectedLabelTextStyle: TextStyle(color: AppColors.text),
        unselectedLabelTextStyle: TextStyle(color: AppColors.text),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.forestSoft,
          foregroundColor: AppColors.text,
          minimumSize: const Size(48, 48),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
          textStyle: base.labelLarge?.copyWith(fontWeight: FontWeight.w700),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.pine,
          minimumSize: const Size(48, 48),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
          side: const BorderSide(color: AppColors.pine),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: AppColors.gold),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(foregroundColor: AppColors.gold),
      ),
      popupMenuTheme: PopupMenuThemeData(
        color: AppColors.surface,
        textStyle: base.bodyLarge?.copyWith(color: AppColors.text),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: AppColors.surface,
        modalBackgroundColor: AppColors.surface,
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.surface,
        contentTextStyle: base.bodyMedium?.copyWith(color: AppColors.text),
        actionTextColor: AppColors.gold,
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AppColors.gold,
        linearTrackColor: AppColors.line,
      ),
      iconTheme: const IconThemeData(color: AppColors.text),
      dividerColor: AppColors.line,
    );
  }
}
