import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

abstract final class AppColors {
  static const canvas = Color(0xFFF6FBF5);
  static const surface = Color(0xFFFFFFFF);
  static const forest = Color(0xFF012D1D);
  static const forestSoft = Color(0xFF1B4332);
  static const pine = Color(0xFF2C694E);
  static const mint = Color(0xFFAEEECB);
  static const text = Color(0xFF181D1A);
  static const muted = Color(0xFF59615C);
  static const line = Color(0xFFDDE5DE);
  static const soft = Color(0xFFF0F5F0);
  static const coral = Color(0xFFBA4A36);
  static const coralSoft = Color(0xFFFBE8E3);
  static const gold = Color(0xFFD4A373);
}

abstract final class AppTheme {
  static ThemeData get light {
    final base = GoogleFonts.manropeTextTheme();
    return ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: AppColors.canvas,
      colorScheme: ColorScheme.fromSeed(
        seedColor: AppColors.forestSoft,
        primary: AppColors.forest,
        secondary: AppColors.pine,
        surface: AppColors.surface,
        error: AppColors.coral,
      ),
      textTheme: base.copyWith(
        headlineMedium: GoogleFonts.literata(
          fontSize: 24,
          height: 1.2,
          fontWeight: FontWeight.w600,
          color: AppColors.forest,
        ),
        headlineSmall: GoogleFonts.literata(
          fontSize: 21,
          height: 1.25,
          fontWeight: FontWeight.w600,
          color: AppColors.forest,
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
          borderSide: const BorderSide(color: AppColors.forest, width: 1.5),
        ),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.surface,
        indicatorColor: AppColors.mint.withOpacity(0.55),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return base.labelSmall?.copyWith(
            color: selected ? AppColors.forest : AppColors.muted,
            fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
          );
        }),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.forest,
          foregroundColor: Colors.white,
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
      dividerColor: AppColors.line,
    );
  }
}
