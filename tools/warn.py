#!/usr/bin/env python
# This file uses the following encoding: utf-8

import argparse
import re

parser = argparse.ArgumentParser(description='Convert a build log into HTML')
parser.add_argument('--gencsv',
                    help='Generate a CSV file with number of various warnings',
                    action="store_true",
                    default=False)
parser.add_argument('--byproject',
                    help='Separate warnings in HTML output by project names',
                    action="store_true",
                    default=False)
parser.add_argument('--url',
                    help='Root URL of an Android source code tree prefixed '
                    'before files in warnings')
parser.add_argument('--separator',
                    help='Separator between the end of a URL and the line '
                    'number argument. e.g. #')
parser.add_argument(dest='buildlog', metavar='build.log',
                    help='Path to build.log file')
args = parser.parse_args()

# if you add another level, don't forget to give it a color below
class severity:
    UNKNOWN = 0
    FIXMENOW = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    TIDY = 5
    HARMLESS = 6
    SKIP = 7
    attributes = [
        ['lightblue', 'Unknown',   'Unknown warnings'],
        ['fuchsia',   'FixNow',    'Critical warnings, fix me now'],
        ['red',       'High',      'High severity warnings'],
        ['orange',    'Medium',    'Medium severity warnings'],
        ['yellow',    'Low',       'Low severity warnings'],
        ['peachpuff', 'Tidy',      'Clang-Tidy warnings'],
        ['limegreen', 'Harmless',  'Harmless warnings'],
        ['grey',      'Unhandled', 'Unhandled warnings']
    ]
    color = [a[0] for a in attributes]
    columnheader = [a[1] for a in attributes]
    header = [a[2] for a in attributes]
    # order to dump by severity
    kinds = [FIXMENOW, HIGH, MEDIUM, LOW, TIDY, HARMLESS, UNKNOWN, SKIP]

warnpatterns = [
    { 'category':'make',    'severity':severity.MEDIUM,
        'description':'make: overriding commands/ignoring old commands',
        'patterns':[r".*: warning: overriding commands for target .+",
                    r".*: warning: ignoring old commands for target .+"] },
    { 'category':'make',    'severity':severity.HIGH,
        'description':'make: LOCAL_CLANG is false',
        'patterns':[r".*: warning: LOCAL_CLANG is set to false"] },
    { 'category':'make',    'severity':severity.HIGH,
        'description':'SDK App using platform shared library',
        'patterns':[r".*: warning: .+ \(.*app:sdk.*\) should not link to .+ \(native:platform\)"] },
    { 'category':'make',    'severity':severity.HIGH,
        'description':'System module linking to a vendor module',
        'patterns':[r".*: warning: .+ \(.+\) should not link to .+ \(partition:.+\)"] },
    { 'category':'make',    'severity':severity.MEDIUM,
        'description':'Invalid SDK/NDK linking',
        'patterns':[r".*: warning: .+ \(.+\) should not link to .+ \(.+\)"] },
    { 'category':'C/C++',   'severity':severity.HIGH, 'option':'-Wimplicit-function-declaration',
        'description':'Implicit function declaration',
        'patterns':[r".*: warning: implicit declaration of function .+",
                    r".*: warning: implicitly declaring library function" ] },
    { 'category':'C/C++',   'severity':severity.SKIP,
        'description':'',
        'patterns':[r".*: warning: conflicting types for '.+'"] },
    { 'category':'C/C++',   'severity':severity.HIGH, 'option':'-Wtype-limits',
        'description':'Expression always evaluates to true or false',
        'patterns':[r".*: warning: comparison is always .+ due to limited range of data type",
                    r".*: warning: comparison of unsigned .*expression .+ is always true",
                    r".*: warning: comparison of unsigned .*expression .+ is always false"] },
    { 'category':'C/C++',   'severity':severity.HIGH,
        'description':'Potential leak of memory, bad free, use after free',
        'patterns':[r".*: warning: Potential leak of memory",
                    r".*: warning: Potential memory leak",
                    r".*: warning: Memory allocated by alloca\(\) should not be deallocated",
                    r".*: warning: Memory allocated by .+ should be deallocated by .+ not .+",
                    r".*: warning: 'delete' applied to a pointer that was allocated",
                    r".*: warning: Use of memory after it is freed",
                    r".*: warning: Argument to .+ is the address of .+ variable",
                    r".*: warning: Argument to free\(\) is offset by .+ of memory allocated by",
                    r".*: warning: Attempt to .+ released memory"] },
    { 'category':'C/C++',   'severity':severity.HIGH,
        'description':'Use transient memory for control value',
        'patterns':[r".*: warning: .+Using such transient memory for the control value is .*dangerous."] },
    { 'category':'C/C++',   'severity':severity.HIGH,
        'description':'Return address of stack memory',
        'patterns':[r".*: warning: Address of stack memory .+ returned to caller",
                    r".*: warning: Address of stack memory .+ will be a dangling reference"] },
    { 'category':'C/C++',   'severity':severity.HIGH,
        'description':'Problem with vfork',
        'patterns':[r".*: warning: This .+ is prohibited after a successful vfork",
                    r".*: warning: Call to function '.+' is insecure "] },
    { 'category':'C/C++',   'severity':severity.HIGH, 'option':'infinite-recursion',
        'description':'Infinite recursion',
        'patterns':[r".*: warning: all paths through this function will call itself"] },
    { 'category':'C/C++',   'severity':severity.HIGH,
        'description':'Potential buffer overflow',
        'patterns':[r".*: warning: Size argument is greater than .+ the destination buffer",
                    r".*: warning: Potential buffer overflow.",
                    r".*: warning: String copy function overflows destination buffer"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Incompatible pointer types',
        'patterns':[r".*: warning: assignment from incompatible pointer type",
                    r".*: warning: return from incompatible pointer type",
                    r".*: warning: passing argument [0-9]+ of '.*' from incompatible pointer type",
                    r".*: warning: initialization from incompatible pointer type"] },
    { 'category':'C/C++',   'severity':severity.HIGH, 'option':'-fno-builtin',
        'description':'Incompatible declaration of built in function',
        'patterns':[r".*: warning: incompatible implicit declaration of built-in function .+"] },
    { 'category':'C/C++',   'severity':severity.HIGH, 'option':'-Wincompatible-library-redeclaration',
        'description':'Incompatible redeclaration of library function',
        'patterns':[r".*: warning: incompatible redeclaration of library function .+"] },
    { 'category':'C/C++',   'severity':severity.HIGH,
        'description':'Null passed as non-null argument',
        'patterns':[r".*: warning: Null passed to a callee that requires a non-null"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wunused-parameter',
        'description':'Unused parameter',
        'patterns':[r".*: warning: unused parameter '.*'"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wunused',
        'description':'Unused function, variable or label',
        'patterns':[r".*: warning: '.+' defined but not used",
                    r".*: warning: unused function '.+'",
                    r".*: warning: private field '.+' is not used",
                    r".*: warning: unused variable '.+'"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wunused-value',
        'description':'Statement with no effect or result unused',
        'patterns':[r".*: warning: statement with no effect",
                    r".*: warning: expression result unused"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wunused-result',
        'description':'Ignoreing return value of function',
        'patterns':[r".*: warning: ignoring return value of function .+Wunused-result"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wmissing-field-initializers',
        'description':'Missing initializer',
        'patterns':[r".*: warning: missing initializer"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wdelete-non-virtual-dtor',
        'description':'Need virtual destructor',
        'patterns':[r".*: warning: delete called .* has virtual functions but non-virtual destructor"] },
    { 'category':'cont.',   'severity':severity.SKIP,
        'description':'',
        'patterns':[r".*: warning: \(near initialization for '.+'\)"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wdate-time',
        'description':'Expansion of data or time macro',
        'patterns':[r".*: warning: expansion of date or time macro is not reproducible"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wformat',
        'description':'Format string does not match arguments',
        'patterns':[r".*: warning: format '.+' expects type '.+', but argument [0-9]+ has type '.+'",
                    r".*: warning: more '%' conversions than data arguments",
                    r".*: warning: data argument not used by format string",
                    r".*: warning: incomplete format specifier",
                    r".*: warning: unknown conversion type .* in format",
                    r".*: warning: format .+ expects .+ but argument .+Wformat=",
                    r".*: warning: field precision should have .+ but argument has .+Wformat",
                    r".*: warning: format specifies type .+ but the argument has .*type .+Wformat"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wformat-extra-args',
        'description':'Too many arguments for format string',
        'patterns':[r".*: warning: too many arguments for format"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wformat-invalid-specifier',
        'description':'Invalid format specifier',
        'patterns':[r".*: warning: invalid .+ specifier '.+'.+format-invalid-specifier"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wsign-compare',
        'description':'Comparison between signed and unsigned',
        'patterns':[r".*: warning: comparison between signed and unsigned",
                    r".*: warning: comparison of promoted \~unsigned with unsigned",
                    r".*: warning: signed and unsigned type in conditional expression"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Comparison between enum and non-enum',
        'patterns':[r".*: warning: enumeral and non-enumeral type in conditional expression"] },
    { 'category':'libpng',  'severity':severity.MEDIUM,
        'description':'libpng: zero area',
        'patterns':[r".*libpng warning: Ignoring attempt to set cHRM RGB triangle with zero area"] },
    { 'category':'aapt',    'severity':severity.MEDIUM,
        'description':'aapt: no comment for public symbol',
        'patterns':[r".*: warning: No comment for public symbol .+"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wmissing-braces',
        'description':'Missing braces around initializer',
        'patterns':[r".*: warning: missing braces around initializer.*"] },
    { 'category':'C/C++',   'severity':severity.HARMLESS,
        'description':'No newline at end of file',
        'patterns':[r".*: warning: no newline at end of file"] },
    { 'category':'C/C++',   'severity':severity.HARMLESS,
        'description':'Missing space after macro name',
        'patterns':[r".*: warning: missing whitespace after the macro name"] },
    { 'category':'C/C++',   'severity':severity.LOW, 'option':'-Wcast-align',
        'description':'Cast increases required alignment',
        'patterns':[r".*: warning: cast from .* to .* increases required alignment .*"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wcast-qual',
        'description':'Qualifier discarded',
        'patterns':[r".*: warning: passing argument [0-9]+ of '.+' discards qualifiers from pointer target type",
                    r".*: warning: assignment discards qualifiers from pointer target type",
                    r".*: warning: passing .+ to parameter of type .+ discards qualifiers",
                    r".*: warning: assigning to .+ from .+ discards qualifiers",
                    r".*: warning: initializing .+ discards qualifiers .+types-discards-qualifiers",
                    r".*: warning: return discards qualifiers from pointer target type"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wunknown-attributes',
        'description':'Unknown attribute',
        'patterns':[r".*: warning: unknown attribute '.+'"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wignored-attributes',
        'description':'Attribute ignored',
        'patterns':[r".*: warning: '_*packed_*' attribute ignored",
                    r".*: warning: attribute declaration must precede definition .+ignored-attributes"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wvisibility',
        'description':'Visibility problem',
        'patterns':[r".*: warning: declaration of '.+' will not be visible outside of this function"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wattributes',
        'description':'Visibility mismatch',
        'patterns':[r".*: warning: '.+' declared with greater visibility than the type of its field '.+'"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Shift count greater than width of type',
        'patterns':[r".*: warning: (left|right) shift count >= width of type"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wextern-initializer',
        'description':'extern &lt;foo&gt; is initialized',
        'patterns':[r".*: warning: '.+' initialized and declared 'extern'",
                    r".*: warning: 'extern' variable has an initializer"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wold-style-declaration',
        'description':'Old style declaration',
        'patterns':[r".*: warning: 'static' is not at beginning of declaration"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wreturn-type',
        'description':'Missing return value',
        'patterns':[r".*: warning: control reaches end of non-void function"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wimplicit-int',
        'description':'Implicit int type',
        'patterns':[r".*: warning: type specifier missing, defaults to 'int'",
                    r".*: warning: type defaults to 'int' in declaration of '.+'"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wmain-return-type',
        'description':'Main function should return int',
        'patterns':[r".*: warning: return type of 'main' is not 'int'"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wuninitialized',
        'description':'Variable may be used uninitialized',
        'patterns':[r".*: warning: '.+' may be used uninitialized in this function"] },
    { 'category':'C/C++',   'severity':severity.HIGH, 'option':'-Wuninitialized',
        'description':'Variable is used uninitialized',
        'patterns':[r".*: warning: '.+' is used uninitialized in this function",
                    r".*: warning: variable '.+' is uninitialized when used here"] },
    { 'category':'ld',      'severity':severity.MEDIUM, 'option':'-fshort-enums',
        'description':'ld: possible enum size mismatch',
        'patterns':[r".*: warning: .* uses variable-size enums yet the output is to use 32-bit enums; use of enum values across objects may fail"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wpointer-sign',
        'description':'Pointer targets differ in signedness',
        'patterns':[r".*: warning: pointer targets in initialization differ in signedness",
                    r".*: warning: pointer targets in assignment differ in signedness",
                    r".*: warning: pointer targets in return differ in signedness",
                    r".*: warning: pointer targets in passing argument [0-9]+ of '.+' differ in signedness"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wstrict-overflow',
        'description':'Assuming overflow does not occur',
        'patterns':[r".*: warning: assuming signed overflow does not occur when assuming that .* is always (true|false)"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wempty-body',
        'description':'Suggest adding braces around empty body',
        'patterns':[r".*: warning: suggest braces around empty body in an 'if' statement",
                    r".*: warning: empty body in an if-statement",
                    r".*: warning: suggest braces around empty body in an 'else' statement",
                    r".*: warning: empty body in an else-statement"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wparentheses',
        'description':'Suggest adding parentheses',
        'patterns':[r".*: warning: suggest explicit braces to avoid ambiguous 'else'",
                    r".*: warning: suggest parentheses around arithmetic in operand of '.+'",
                    r".*: warning: suggest parentheses around comparison in operand of '.+'",
                    r".*: warning: logical not is only applied to the left hand side of this comparison",
                    r".*: warning: using the result of an assignment as a condition without parentheses",
                    r".*: warning: .+ has lower precedence than .+ be evaluated first .+Wparentheses",
                    r".*: warning: suggest parentheses around '.+?' .+ '.+?'",
                    r".*: warning: suggest parentheses around assignment used as truth value"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Static variable used in non-static inline function',
        'patterns':[r".*: warning: '.+' is static but used in inline function '.+' which is not static"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wimplicit int',
        'description':'No type or storage class (will default to int)',
        'patterns':[r".*: warning: data definition has no type or storage class"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Null pointer',
        'patterns':[r".*: warning: Dereference of null pointer",
                    r".*: warning: Called .+ pointer is null",
                    r".*: warning: Forming reference to null pointer",
                    r".*: warning: Returning null reference",
                    r".*: warning: Null pointer passed as an argument to a 'nonnull' parameter",
                    r".*: warning: .+ results in a null pointer dereference",
                    r".*: warning: Access to .+ results in a dereference of a null pointer",
                    r".*: warning: Null pointer argument in"] },
    { 'category':'cont.',   'severity':severity.SKIP,
        'description':'',
        'patterns':[r".*: warning: parameter names \(without types\) in function declaration"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wstrict-aliasing',
        'description':'Dereferencing &lt;foo&gt; breaks strict aliasing rules',
        'patterns':[r".*: warning: dereferencing .* break strict-aliasing rules"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wpointer-to-int-cast',
        'description':'Cast from pointer to integer of different size',
        'patterns':[r".*: warning: cast from pointer to integer of different size",
                    r".*: warning: initialization makes pointer from integer without a cast"] } ,
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wint-to-pointer-cast',
        'description':'Cast to pointer from integer of different size',
        'patterns':[r".*: warning: cast to pointer from integer of different size"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Symbol redefined',
        'patterns':[r".*: warning: "".+"" redefined"] },
    { 'category':'cont.',   'severity':severity.SKIP,
        'description':'',
        'patterns':[r".*: warning: this is the location of the previous definition"] },
    { 'category':'ld',      'severity':severity.MEDIUM,
        'description':'ld: type and size of dynamic symbol are not defined',
        'patterns':[r".*: warning: type and size of dynamic symbol `.+' are not defined"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Pointer from integer without cast',
        'patterns':[r".*: warning: assignment makes pointer from integer without a cast"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Pointer from integer without cast',
        'patterns':[r".*: warning: passing argument [0-9]+ of '.+' makes pointer from integer without a cast"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Integer from pointer without cast',
        'patterns':[r".*: warning: assignment makes integer from pointer without a cast"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Integer from pointer without cast',
        'patterns':[r".*: warning: passing argument [0-9]+ of '.+' makes integer from pointer without a cast"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Integer from pointer without cast',
        'patterns':[r".*: warning: return makes integer from pointer without a cast"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wunknown-pragmas',
        'description':'Ignoring pragma',
        'patterns':[r".*: warning: ignoring #pragma .+"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-W#pragma-messages',
        'description':'Pragma warning messages',
        'patterns':[r".*: warning: .+W#pragma-messages"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wclobbered',
        'description':'Variable might be clobbered by longjmp or vfork',
        'patterns':[r".*: warning: variable '.+' might be clobbered by 'longjmp' or 'vfork'"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wclobbered',
        'description':'Argument might be clobbered by longjmp or vfork',
        'patterns':[r".*: warning: argument '.+' might be clobbered by 'longjmp' or 'vfork'"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wredundant-decls',
        'description':'Redundant declaration',
        'patterns':[r".*: warning: redundant redeclaration of '.+'"] },
    { 'category':'cont.',   'severity':severity.SKIP,
        'description':'',
        'patterns':[r".*: warning: previous declaration of '.+' was here"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wswitch-enum',
        'description':'Enum value not handled in switch',
        'patterns':[r".*: warning: .*enumeration value.* not handled in switch.+Wswitch"] },
    { 'category':'java',    'severity':severity.MEDIUM, 'option':'-encoding',
        'description':'Java: Non-ascii characters used, but ascii encoding specified',
        'patterns':[r".*: warning: unmappable character for encoding ascii"] },
    { 'category':'java',    'severity':severity.MEDIUM,
        'description':'Java: Non-varargs call of varargs method with inexact argument type for last parameter',
        'patterns':[r".*: warning: non-varargs call of varargs method with inexact argument type for last parameter"] },
    { 'category':'java',    'severity':severity.MEDIUM,
        'description':'Java: Unchecked method invocation',
        'patterns':[r".*: warning: \[unchecked\] unchecked method invocation: .+ in class .+"] },
    { 'category':'java',    'severity':severity.MEDIUM,
        'description':'Java: Unchecked conversion',
        'patterns':[r".*: warning: \[unchecked\] unchecked conversion"] },
    { 'category':'java',   'severity':severity.MEDIUM,
        'description':'_ used as an identifier',
        'patterns':[r".*: warning: '_' used as an identifier"] },

    # Warnings from Error Prone.
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description': 'Java: Use of deprecated member',
     'patterns': [r'.*: warning: \[deprecation\] .+']},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description': 'Java: Unchecked conversion',
     'patterns': [r'.*: warning: \[unchecked\] .+']},

    # Warnings from Error Prone (auto generated list).
    {'category': 'java',
     'severity': severity.LOW,
     'description':
         'Java: Deprecated item is not annotated with @Deprecated',
     'patterns': [r".*: warning: \[DepAnn\] .+"]},
    {'category': 'java',
     'severity': severity.LOW,
     'description':
         'Java: Fallthrough warning suppression has no effect if warning is suppressed',
     'patterns': [r".*: warning: \[FallthroughSuppression\] .+"]},
    {'category': 'java',
     'severity': severity.LOW,
     'description':
         'Java: Prefer \'L\' to \'l\' for the suffix to long literals',
     'patterns': [r".*: warning: \[LongLiteralLowerCaseSuffix\] .+"]},
    {'category': 'java',
     'severity': severity.LOW,
     'description':
         'Java: @Binds is a more efficient and declaritive mechanism for delegating a binding.',
     'patterns': [r".*: warning: \[UseBinds\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Assertions may be disabled at runtime and do not guarantee that execution will halt here; consider throwing an exception instead',
     'patterns': [r".*: warning: \[AssertFalse\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Classes that implement Annotation must override equals and hashCode. Consider using AutoAnnotation instead of implementing Annotation by hand.',
     'patterns': [r".*: warning: \[BadAnnotationImplementation\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: BigDecimal(double) and BigDecimal.valueOf(double) may lose precision, prefer BigDecimal(String) or BigDecimal(long)',
     'patterns': [r".*: warning: \[BigDecimalLiteralDouble\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Mockito cannot mock final classes',
     'patterns': [r".*: warning: \[CannotMockFinalClass\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: This code, which counts elements using a loop, can be replaced by a simpler library method',
     'patterns': [r".*: warning: \[ElementsCountedInLoop\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Empty top-level type declaration',
     'patterns': [r".*: warning: \[EmptyTopLevelDeclaration\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Classes that override equals should also override hashCode.',
     'patterns': [r".*: warning: \[EqualsHashCode\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: An equality test between objects with incompatible types always returns false',
     'patterns': [r".*: warning: \[EqualsIncompatibleType\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: If you return or throw from a finally, then values returned or thrown from the try-catch block will be ignored. Consider using try-with-resources instead.',
     'patterns': [r".*: warning: \[Finally\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: This annotation has incompatible modifiers as specified by its @IncompatibleModifiers annotation',
     'patterns': [r".*: warning: \[IncompatibleModifiers\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Class should not implement both `Iterable` and `Iterator`',
     'patterns': [r".*: warning: \[IterableAndIterator\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Floating-point comparison without error tolerance',
     'patterns': [r".*: warning: \[JUnit3FloatingPointComparisonWithoutDelta\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Test class inherits from JUnit 3\'s TestCase but has JUnit 4 @Test annotations.',
     'patterns': [r".*: warning: \[JUnitAmbiguousTestClass\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Enum switch statement is missing cases',
     'patterns': [r".*: warning: \[MissingCasesInEnumSwitch\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Not calling fail() when expecting an exception masks bugs',
     'patterns': [r".*: warning: \[MissingFail\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: method overrides method in supertype; expected @Override',
     'patterns': [r".*: warning: \[MissingOverride\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Source files should not contain multiple top-level class declarations',
     'patterns': [r".*: warning: \[MultipleTopLevelClasses\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: This update of a volatile variable is non-atomic',
     'patterns': [r".*: warning: \[NonAtomicVolatileUpdate\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Static import of member uses non-canonical name',
     'patterns': [r".*: warning: \[NonCanonicalStaticMemberImport\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: equals method doesn\'t override Object.equals',
     'patterns': [r".*: warning: \[NonOverridingEquals\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Constructors should not be annotated with @Nullable since they cannot return null',
     'patterns': [r".*: warning: \[NullableConstructor\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: @Nullable should not be used for primitive types since they cannot be null',
     'patterns': [r".*: warning: \[NullablePrimitive\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: void-returning methods should not be annotated with @Nullable, since they cannot return null',
     'patterns': [r".*: warning: \[NullableVoid\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Package names should match the directory they are declared in',
     'patterns': [r".*: warning: \[PackageLocation\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Second argument to Preconditions.* is a call to String.format(), which can be unwrapped',
     'patterns': [r".*: warning: \[PreconditionsErrorMessageEagerEvaluation\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Preconditions only accepts the %s placeholder in error message strings',
     'patterns': [r".*: warning: \[PreconditionsInvalidPlaceholder\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Passing a primitive array to a varargs method is usually wrong',
     'patterns': [r".*: warning: \[PrimitiveArrayPassedToVarargsMethod\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Protobuf fields cannot be null, so this check is redundant',
     'patterns': [r".*: warning: \[ProtoFieldPreconditionsCheckNotNull\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: This annotation is missing required modifiers as specified by its @RequiredModifiers annotation',
     'patterns': [r".*: warning: \[RequiredModifiers\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: A static variable or method should not be accessed from an object instance',
     'patterns': [r".*: warning: \[StaticAccessedFromInstance\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: String comparison using reference equality instead of value equality',
     'patterns': [r".*: warning: \[StringEquality\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Declaring a type parameter that is only used in the return type is a misuse of generics: operations on the type parameter are unchecked, it hides unsafe casts at invocations of the method, and it interacts badly with method overload resolution.',
     'patterns': [r".*: warning: \[TypeParameterUnusedInFormals\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Using static imports for types is unnecessary',
     'patterns': [r".*: warning: \[UnnecessaryStaticImport\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Unsynchronized method overrides a synchronized method.',
     'patterns': [r".*: warning: \[UnsynchronizedOverridesSynchronized\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Non-constant variable missing @Var annotation',
     'patterns': [r".*: warning: \[Var\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Because of spurious wakeups, Object.wait() and Condition.await() must always be called in a loop',
     'patterns': [r".*: warning: \[WaitNotInLoop\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Subclasses of Fragment must be instantiable via Class#newInstance(): the class must be public, static and have a public nullary constructor',
     'patterns': [r".*: warning: \[FragmentNotInstantiable\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Hardcoded reference to /sdcard',
     'patterns': [r".*: warning: \[HardCodedSdCardPath\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Incompatible type as argument to Object-accepting Java collections method',
     'patterns': [r".*: warning: \[CollectionIncompatibleType\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: @AssistedInject and @Inject should not be used on different constructors in the same class.',
     'patterns': [r".*: warning: \[AssistedInjectAndInjectOnConstructors\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Although Guice allows injecting final fields, doing so is not recommended because the injected value may not be visible to other threads.',
     'patterns': [r".*: warning: \[GuiceInjectOnFinalField\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: This method is not annotated with @Inject, but it overrides a method that is annotated with @com.google.inject.Inject. Guice will inject this method, and it is recommended to annotate it explicitly.',
     'patterns': [r".*: warning: \[OverridesGuiceInjectableMethod\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Double-checked locking on non-volatile fields is unsafe',
     'patterns': [r".*: warning: \[DoubleCheckedLocking\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Writes to static fields should not be guarded by instance locks',
     'patterns': [r".*: warning: \[StaticGuardedByInstance\] .+"]},
    {'category': 'java',
     'severity': severity.MEDIUM,
     'description':
         'Java: Synchronizing on non-final fields is not safe: if the field is ever updated, different threads may end up locking on different objects.',
     'patterns': [r".*: warning: \[SynchronizeOnNonFinalField\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Reference equality used to compare arrays',
     'patterns': [r".*: warning: \[ArrayEquals\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: hashcode method on array does not hash array contents',
     'patterns': [r".*: warning: \[ArrayHashCode\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Calling toString on an array does not provide useful information',
     'patterns': [r".*: warning: \[ArrayToString.*\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Arrays.asList does not autobox primitive arrays, as one might expect.',
     'patterns': [r".*: warning: \[ArraysAsListPrimitiveArray\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: AsyncCallable should not return a null Future, only a Future whose result is null.',
     'patterns': [r".*: warning: \[AsyncCallableReturnsNull\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: AsyncFunction should not return a null Future, only a Future whose result is null.',
     'patterns': [r".*: warning: \[AsyncFunctionReturnsNull\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Possible sign flip from narrowing conversion',
     'patterns': [r".*: warning: \[BadComparable\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Shift by an amount that is out of range',
     'patterns': [r".*: warning: \[BadShiftAmount\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: valueOf provides better time and space performance',
     'patterns': [r".*: warning: \[BoxedPrimitiveConstructor\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: The called constructor accepts a parameter with the same name and type as one of its caller\'s parameters, but its caller doesn\'t pass that parameter to it.  It\'s likely that it was intended to.',
     'patterns': [r".*: warning: \[ChainingConstructorIgnoresParameter\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Ignored return value of method that is annotated with @CheckReturnValue',
     'patterns': [r".*: warning: \[CheckReturnValue\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Inner class is non-static but does not reference enclosing class',
     'patterns': [r".*: warning: \[ClassCanBeStatic\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: The source file name should match the name of the top-level class it contains',
     'patterns': [r".*: warning: \[ClassName\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: This comparison method violates the contract',
     'patterns': [r".*: warning: \[ComparisonContractViolated\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Comparison to value that is out of range for the compared type',
     'patterns': [r".*: warning: \[ComparisonOutOfRange\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Non-compile-time constant expression passed to parameter with @CompileTimeConstant type annotation.',
     'patterns': [r".*: warning: \[CompileTimeConstant\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Exception created but not thrown',
     'patterns': [r".*: warning: \[DeadException\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Division by integer literal zero',
     'patterns': [r".*: warning: \[DivZero\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Empty statement after if',
     'patterns': [r".*: warning: \[EmptyIf\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: == NaN always returns false; use the isNaN methods instead',
     'patterns': [r".*: warning: \[EqualsNaN\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Method annotated @ForOverride must be protected or package-private and only invoked from declaring class',
     'patterns': [r".*: warning: \[ForOverride\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Futures.getChecked requires a checked exception type with a standard constructor.',
     'patterns': [r".*: warning: \[FuturesGetCheckedIllegalExceptionType\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Calling getClass() on an object of type Class returns the Class object for java.lang.Class; you probably meant to operate on the object directly',
     'patterns': [r".*: warning: \[GetClassOnClass\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: An object is tested for equality to itself using Guava Libraries',
     'patterns': [r".*: warning: \[GuavaSelfEquals\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: contains() is a legacy method that is equivalent to containsValue()',
     'patterns': [r".*: warning: \[HashtableContains\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Cipher.getInstance() is invoked using either the default settings or ECB mode',
     'patterns': [r".*: warning: \[InsecureCipherMode\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Invalid syntax used for a regular expression',
     'patterns': [r".*: warning: \[InvalidPatternSyntax\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: The argument to Class#isInstance(Object) should not be a Class',
     'patterns': [r".*: warning: \[IsInstanceOfClass\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: jMock tests must have a @RunWith(JMock.class) annotation, or the Mockery field must have a @Rule JUnit annotation',
     'patterns': [r".*: warning: \[JMockTestWithoutRunWithOrRuleAnnotation\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Test method will not be run; please prefix name with "test"',
     'patterns': [r".*: warning: \[JUnit3TestNotRun\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: setUp() method will not be run; Please add a @Before annotation',
     'patterns': [r".*: warning: \[JUnit4SetUpNotRun\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: tearDown() method will not be run; Please add an @After annotation',
     'patterns': [r".*: warning: \[JUnit4TearDownNotRun\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Test method will not be run; please add @Test annotation',
     'patterns': [r".*: warning: \[JUnit4TestNotRun\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Printf-like format string does not match its arguments',
     'patterns': [r".*: warning: \[MalformedFormatString\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Use of "YYYY" (week year) in a date pattern without "ww" (week in year). You probably meant to use "yyyy" (year) instead.',
     'patterns': [r".*: warning: \[MisusedWeekYear\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: A bug in Mockito will cause this test to fail at runtime with a ClassCastException',
     'patterns': [r".*: warning: \[MockitoCast\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Missing method call for verify(mock) here',
     'patterns': [r".*: warning: \[MockitoUsage\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Modifying a collection with itself',
     'patterns': [r".*: warning: \[ModifyingCollectionWithItself\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Compound assignments to bytes, shorts, chars, and floats hide dangerous casts',
     'patterns': [r".*: warning: \[NarrowingCompoundAssignment\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: @NoAllocation was specified on this method, but something was found that would trigger an allocation',
     'patterns': [r".*: warning: \[NoAllocation\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Static import of type uses non-canonical name',
     'patterns': [r".*: warning: \[NonCanonicalStaticImport\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: @CompileTimeConstant parameters should be final',
     'patterns': [r".*: warning: \[NonFinalCompileTimeConstant\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Calling getAnnotation on an annotation that is not retained at runtime.',
     'patterns': [r".*: warning: \[NonRuntimeAnnotation\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Numeric comparison using reference equality instead of value equality',
     'patterns': [r".*: warning: \[NumericEquality\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Comparison using reference equality instead of value equality',
     'patterns': [r".*: warning: \[OptionalEquality\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Varargs doesn\'t agree for overridden method',
     'patterns': [r".*: warning: \[Overrides\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Literal passed as first argument to Preconditions.checkNotNull() can never be null',
     'patterns': [r".*: warning: \[PreconditionsCheckNotNull\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: First argument to `Preconditions.checkNotNull()` is a primitive rather than an object reference',
     'patterns': [r".*: warning: \[PreconditionsCheckNotNullPrimitive\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Protobuf fields cannot be null',
     'patterns': [r".*: warning: \[ProtoFieldNullComparison\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Comparing protobuf fields of type String using reference equality',
     'patterns': [r".*: warning: \[ProtoStringFieldReferenceEquality\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java:  Check for non-whitelisted callers to RestrictedApiChecker.',
     'patterns': [r".*: warning: \[RestrictedApiChecker\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Return value of this method must be used',
     'patterns': [r".*: warning: \[ReturnValueIgnored\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Variable assigned to itself',
     'patterns': [r".*: warning: \[SelfAssignment\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: An object is compared to itself',
     'patterns': [r".*: warning: \[SelfComparision\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Variable compared to itself',
     'patterns': [r".*: warning: \[SelfEquality\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: An object is tested for equality to itself',
     'patterns': [r".*: warning: \[SelfEquals\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Comparison of a size >= 0 is always true, did you intend to check for non-emptiness?',
     'patterns': [r".*: warning: \[SizeGreaterThanOrEqualsZero\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Calling toString on a Stream does not provide useful information',
     'patterns': [r".*: warning: \[StreamToString\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: StringBuilder does not have a char constructor; this invokes the int constructor.',
     'patterns': [r".*: warning: \[StringBuilderInitWithChar\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Suppressing "deprecated" is probably a typo for "deprecation"',
     'patterns': [r".*: warning: \[SuppressWarningsDeprecated\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: throwIfUnchecked(knownCheckedException) is a no-op.',
     'patterns': [r".*: warning: \[ThrowIfUncheckedKnownChecked\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Catching Throwable/Error masks failures from fail() or assert*() in the try block',
     'patterns': [r".*: warning: \[TryFailThrowable\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Type parameter used as type qualifier',
     'patterns': [r".*: warning: \[TypeParameterQualifier\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Non-generic methods should not be invoked with type arguments',
     'patterns': [r".*: warning: \[UnnecessaryTypeArgument\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Instance created but never used',
     'patterns': [r".*: warning: \[UnusedAnonymousClass\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Use of wildcard imports is forbidden',
     'patterns': [r".*: warning: \[WildcardImport\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Method parameter has wrong package',
     'patterns': [r".*: warning: \[ParameterPackage\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Certain resources in `android.R.string` have names that do not match their content',
     'patterns': [r".*: warning: \[MislabeledAndroidString\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Return value of android.graphics.Rect.intersect() must be checked',
     'patterns': [r".*: warning: \[RectIntersectReturnValueIgnored\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Invalid printf-style format string',
     'patterns': [r".*: warning: \[FormatString\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: @AssistedInject and @Inject cannot be used on the same constructor.',
     'patterns': [r".*: warning: \[AssistedInjectAndInjectOnSameConstructor\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Injected constructors cannot be optional nor have binding annotations',
     'patterns': [r".*: warning: \[InjectedConstructorAnnotations\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: The target of a scoping annotation must be set to METHOD and/or TYPE.',
     'patterns': [r".*: warning: \[InjectInvalidTargetingOnScopingAnnotation\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Abstract methods are not injectable with javax.inject.Inject.',
     'patterns': [r".*: warning: \[JavaxInjectOnAbstractMethod\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: @javax.inject.Inject cannot be put on a final field.',
     'patterns': [r".*: warning: \[JavaxInjectOnFinalField\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: A class may not have more than one injectable constructor.',
     'patterns': [r".*: warning: \[MoreThanOneInjectableConstructor\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Using more than one qualifier annotation on the same element is not allowed.',
     'patterns': [r".*: warning: \[InjectMoreThanOneQualifier\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: A class can be annotated with at most one scope annotation',
     'patterns': [r".*: warning: \[InjectMoreThanOneScopeAnnotationOnClass\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Annotations cannot be both Qualifiers/BindingAnnotations and Scopes',
     'patterns': [r".*: warning: \[OverlappingQualifierAndScopeAnnotation\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Scope annotation on an interface or abstact class is not allowed',
     'patterns': [r".*: warning: \[InjectScopeAnnotationOnInterfaceOrAbstractClass\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Scoping and qualifier annotations must have runtime retention.',
     'patterns': [r".*: warning: \[InjectScopeOrQualifierAnnotationRetention\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Dagger @Provides methods may not return null unless annotated with @Nullable',
     'patterns': [r".*: warning: \[DaggerProvidesNull\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Scope annotation on implementation class of AssistedInject factory is not allowed',
     'patterns': [r".*: warning: \[GuiceAssistedInjectScoping\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: A constructor cannot have two @Assisted parameters of the same type unless they are disambiguated with named @Assisted annotations. ',
     'patterns': [r".*: warning: \[GuiceAssistedParameters\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: This method is not annotated with @Inject, but it overrides a  method that is  annotated with @javax.inject.Inject.',
     'patterns': [r".*: warning: \[OverridesJavaxInjectableMethod\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Checks for unguarded accesses to fields and methods with @GuardedBy annotations',
     'patterns': [r".*: warning: \[GuardedByChecker\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Invalid @GuardedBy expression',
     'patterns': [r".*: warning: \[GuardedByValidator\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: Type declaration annotated with @Immutable is not immutable',
     'patterns': [r".*: warning: \[Immutable\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: This method does not acquire the locks specified by its @LockMethod annotation',
     'patterns': [r".*: warning: \[LockMethodChecker\] .+"]},
    {'category': 'java',
     'severity': severity.HIGH,
     'description':
         'Java: This method does not acquire the locks specified by its @UnlockMethod annotation',
     'patterns': [r".*: warning: \[UnlockMethod\] .+"]},

    {'category': 'java',
     'severity': severity.UNKNOWN,
     'description': 'Java: Unclassified/unrecognized warnings',
     'patterns': [r".*: warning: \[.+\] .+"]},

    { 'category':'aapt',    'severity':severity.MEDIUM,
        'description':'aapt: No default translation',
        'patterns':[r".*: warning: string '.+' has no default translation in .*"] },
    { 'category':'aapt',    'severity':severity.MEDIUM,
        'description':'aapt: Missing default or required localization',
        'patterns':[r".*: warning: \*\*\*\* string '.+' has no default or required localization for '.+' in .+"] },
    { 'category':'aapt',    'severity':severity.MEDIUM,
        'description':'aapt: String marked untranslatable, but translation exists',
        'patterns':[r".*: warning: string '.+' in .* marked untranslatable but exists in locale '??_??'"] },
    { 'category':'aapt',    'severity':severity.MEDIUM,
        'description':'aapt: empty span in string',
        'patterns':[r".*: warning: empty '.+' span found in text '.+"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Taking address of temporary',
        'patterns':[r".*: warning: taking address of temporary"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Possible broken line continuation',
        'patterns':[r".*: warning: backslash and newline separated by space"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wundefined-var-template',
        'description':'Undefined variable template',
        'patterns':[r".*: warning: instantiation of variable .* no definition is available"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wundefined-inline',
        'description':'Inline function is not defined',
        'patterns':[r".*: warning: inline function '.*' is not defined"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Warray-bounds',
        'description':'Array subscript out of bounds',
        'patterns':[r".*: warning: array subscript is above array bounds",
                    r".*: warning: Array subscript is undefined",
                    r".*: warning: array subscript is below array bounds"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Excess elements in initializer',
        'patterns':[r".*: warning: excess elements in .+ initializer"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Decimal constant is unsigned only in ISO C90',
        'patterns':[r".*: warning: this decimal constant is unsigned only in ISO C90"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wmain',
        'description':'main is usually a function',
        'patterns':[r".*: warning: 'main' is usually a function"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Typedef ignored',
        'patterns':[r".*: warning: 'typedef' was ignored in this declaration"] },
    { 'category':'C/C++',   'severity':severity.HIGH, 'option':'-Waddress',
        'description':'Address always evaluates to true',
        'patterns':[r".*: warning: the address of '.+' will always evaluate as 'true'"] },
    { 'category':'C/C++',   'severity':severity.FIXMENOW,
        'description':'Freeing a non-heap object',
        'patterns':[r".*: warning: attempt to free a non-heap object '.+'"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wchar-subscripts',
        'description':'Array subscript has type char',
        'patterns':[r".*: warning: array subscript .+ type 'char'.+Wchar-subscripts"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Constant too large for type',
        'patterns':[r".*: warning: integer constant is too large for '.+' type"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Woverflow',
        'description':'Constant too large for type, truncated',
        'patterns':[r".*: warning: large integer implicitly truncated to unsigned type"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Winteger-overflow',
        'description':'Overflow in expression',
        'patterns':[r".*: warning: overflow in expression; .*Winteger-overflow"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Woverflow',
        'description':'Overflow in implicit constant conversion',
        'patterns':[r".*: warning: overflow in implicit constant conversion"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Declaration does not declare anything',
        'patterns':[r".*: warning: declaration 'class .+' does not declare anything"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wreorder',
        'description':'Initialization order will be different',
        'patterns':[r".*: warning: '.+' will be initialized after",
                    r".*: warning: field .+ will be initialized after .+Wreorder"] },
    { 'category':'cont.',   'severity':severity.SKIP,
        'description':'',
        'patterns':[r".*: warning:   '.+'"] },
    { 'category':'cont.',   'severity':severity.SKIP,
        'description':'',
        'patterns':[r".*: warning:   base '.+'"] },
    { 'category':'cont.',   'severity':severity.SKIP,
        'description':'',
        'patterns':[r".*: warning:   when initialized here"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wmissing-parameter-type',
        'description':'Parameter type not specified',
        'patterns':[r".*: warning: type of '.+' defaults to 'int'"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wmissing-declarations',
        'description':'Missing declarations',
        'patterns':[r".*: warning: declaration does not declare anything"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wmissing-noreturn',
        'description':'Missing noreturn',
        'patterns':[r".*: warning: function '.*' could be declared with attribute 'noreturn'"] },
    { 'category':'gcc',     'severity':severity.MEDIUM,
        'description':'Invalid option for C file',
        'patterns':[r".*: warning: command line option "".+"" is valid for C\+\+\/ObjC\+\+ but not for C"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'User warning',
        'patterns':[r".*: warning: #warning "".+"""] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wvexing-parse',
        'description':'Vexing parsing problem',
        'patterns':[r".*: warning: empty parentheses interpreted as a function declaration"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wextra',
        'description':'Dereferencing void*',
        'patterns':[r".*: warning: dereferencing 'void \*' pointer"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Comparison of pointer and integer',
        'patterns':[r".*: warning: ordered comparison of pointer with integer zero",
                    r".*: warning: .*comparison between pointer and integer"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Use of error-prone unary operator',
        'patterns':[r".*: warning: use of unary operator that may be intended as compound assignment"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wwrite-strings',
        'description':'Conversion of string constant to non-const char*',
        'patterns':[r".*: warning: deprecated conversion from string constant to '.+'"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wstrict-prototypes',
        'description':'Function declaration isn''t a prototype',
        'patterns':[r".*: warning: function declaration isn't a prototype"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wignored-qualifiers',
        'description':'Type qualifiers ignored on function return value',
        'patterns':[r".*: warning: type qualifiers ignored on function return type",
                    r".*: warning: .+ type qualifier .+ has no effect .+Wignored-qualifiers"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'&lt;foo&gt; declared inside parameter list, scope limited to this definition',
        'patterns':[r".*: warning: '.+' declared inside parameter list"] },
    { 'category':'cont.',   'severity':severity.SKIP,
        'description':'',
        'patterns':[r".*: warning: its scope is only this definition or declaration, which is probably not what you want"] },
    { 'category':'C/C++',   'severity':severity.LOW, 'option':'-Wcomment',
        'description':'Line continuation inside comment',
        'patterns':[r".*: warning: multi-line comment"] },
    { 'category':'C/C++',   'severity':severity.LOW, 'option':'-Wcomment',
        'description':'Comment inside comment',
        'patterns':[r".*: warning: "".+"" within comment"] },
    # Warning "value stored is never read" could be from clang-tidy or clang static analyzer.
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy Value stored is never read',
        'patterns':[r".*: warning: Value stored to .+ is never read.*clang-analyzer-deadcode.DeadStores"] },
    { 'category':'C/C++',   'severity':severity.LOW,
        'description':'Value stored is never read',
        'patterns':[r".*: warning: Value stored to .+ is never read"] },
    { 'category':'C/C++',   'severity':severity.LOW, 'option':'-Wdeprecated-declarations',
        'description':'Deprecated declarations',
        'patterns':[r".*: warning: .+ is deprecated.+deprecated-declarations"] },
    { 'category':'C/C++',   'severity':severity.LOW, 'option':'-Wdeprecated-register',
        'description':'Deprecated register',
        'patterns':[r".*: warning: 'register' storage class specifier is deprecated"] },
    { 'category':'C/C++',   'severity':severity.LOW, 'option':'-Wpointer-sign',
        'description':'Converts between pointers to integer types with different sign',
        'patterns':[r".*: warning: .+ converts between pointers to integer types with different sign"] },
    { 'category':'C/C++',   'severity':severity.HARMLESS,
        'description':'Extra tokens after #endif',
        'patterns':[r".*: warning: extra tokens at end of #endif directive"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wenum-compare',
        'description':'Comparison between different enums',
        'patterns':[r".*: warning: comparison between '.+' and '.+'.+Wenum-compare"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wconversion',
        'description':'Conversion may change value',
        'patterns':[r".*: warning: converting negative value '.+' to '.+'",
                    r".*: warning: conversion to '.+' .+ may (alter|change)"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wconversion-null',
        'description':'Converting to non-pointer type from NULL',
        'patterns':[r".*: warning: converting to non-pointer type '.+' from NULL"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wnull-conversion',
        'description':'Converting NULL to non-pointer type',
        'patterns':[r".*: warning: implicit conversion of NULL constant to '.+'"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wnon-literal-null-conversion',
        'description':'Zero used as null pointer',
        'patterns':[r".*: warning: expression .* zero treated as a null pointer constant"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Implicit conversion changes value',
        'patterns':[r".*: warning: implicit conversion .* changes value from .* to .*-conversion"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Passing NULL as non-pointer argument',
        'patterns':[r".*: warning: passing NULL to non-pointer argument [0-9]+ of '.+'"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wctor-dtor-privacy',
        'description':'Class seems unusable because of private ctor/dtor' ,
        'patterns':[r".*: warning: all member functions in class '.+' are private"] },
    # skip this next one, because it only points out some RefBase-based classes where having a private destructor is perfectly fine
    { 'category':'C/C++',   'severity':severity.SKIP, 'option':'-Wctor-dtor-privacy',
        'description':'Class seems unusable because of private ctor/dtor' ,
        'patterns':[r".*: warning: 'class .+' only defines a private destructor and has no friends"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wctor-dtor-privacy',
        'description':'Class seems unusable because of private ctor/dtor' ,
        'patterns':[r".*: warning: 'class .+' only defines private constructors and has no friends"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wgnu-static-float-init',
        'description':'In-class initializer for static const float/double' ,
        'patterns':[r".*: warning: in-class initializer for static data member of .+const (float|double)"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wpointer-arith',
        'description':'void* used in arithmetic' ,
        'patterns':[r".*: warning: pointer of type 'void \*' used in (arithmetic|subtraction)",
                    r".*: warning: arithmetic on .+ to void is a GNU extension.*Wpointer-arith",
                    r".*: warning: wrong type argument to increment"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wsign-promo',
        'description':'Overload resolution chose to promote from unsigned or enum to signed type' ,
        'patterns':[r".*: warning: passing '.+' chooses '.+' over '.+'.*Wsign-promo"] },
    { 'category':'cont.',   'severity':severity.SKIP,
        'description':'',
        'patterns':[r".*: warning:   in call to '.+'"] },
    { 'category':'C/C++',   'severity':severity.HIGH, 'option':'-Wextra',
        'description':'Base should be explicitly initialized in copy constructor',
        'patterns':[r".*: warning: base class '.+' should be explicitly initialized in the copy constructor"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'VLA has zero or negative size',
        'patterns':[r".*: warning: Declared variable-length array \(VLA\) has .+ size"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Return value from void function',
        'patterns':[r".*: warning: 'return' with a value, in function returning void"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'multichar',
        'description':'Multi-character character constant',
        'patterns':[r".*: warning: multi-character character constant"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'writable-strings',
        'description':'Conversion from string literal to char*',
        'patterns':[r".*: warning: .+ does not allow conversion from string literal to 'char \*'"] },
    { 'category':'C/C++',   'severity':severity.LOW, 'option':'-Wextra-semi',
        'description':'Extra \';\'',
        'patterns':[r".*: warning: extra ';' .+extra-semi"] },
    { 'category':'C/C++',   'severity':severity.LOW,
        'description':'Useless specifier',
        'patterns':[r".*: warning: useless storage class specifier in empty declaration"] },
    { 'category':'C/C++',   'severity':severity.LOW, 'option':'-Wduplicate-decl-specifier',
        'description':'Duplicate declaration specifier',
        'patterns':[r".*: warning: duplicate '.+' declaration specifier"] },
    { 'category':'logtags',   'severity':severity.LOW,
        'description':'Duplicate logtag',
        'patterns':[r".*: warning: tag \".+\" \(.+\) duplicated in .+"] },
    { 'category':'logtags',   'severity':severity.LOW, 'option':'typedef-redefinition',
        'description':'Typedef redefinition',
        'patterns':[r".*: warning: redefinition of typedef '.+' is a C11 feature"] },
    { 'category':'logtags',   'severity':severity.LOW, 'option':'gnu-designator',
        'description':'GNU old-style field designator',
        'patterns':[r".*: warning: use of GNU old-style field designator extension"] },
    { 'category':'logtags',   'severity':severity.LOW, 'option':'missing-field-initializers',
        'description':'Missing field initializers',
        'patterns':[r".*: warning: missing field '.+' initializer"] },
    { 'category':'logtags',   'severity':severity.LOW, 'option':'missing-braces',
        'description':'Missing braces',
        'patterns':[r".*: warning: suggest braces around initialization of",
                    r".*: warning: too many braces around scalar initializer .+Wmany-braces-around-scalar-init",
                    r".*: warning: braces around scalar initializer"] },
    { 'category':'logtags',   'severity':severity.LOW, 'option':'sign-compare',
        'description':'Comparison of integers of different signs',
        'patterns':[r".*: warning: comparison of integers of different signs.+sign-compare"] },
    { 'category':'logtags',   'severity':severity.LOW, 'option':'dangling-else',
        'description':'Add braces to avoid dangling else',
        'patterns':[r".*: warning: add explicit braces to avoid dangling else"] },
    { 'category':'logtags',   'severity':severity.LOW, 'option':'initializer-overrides',
        'description':'Initializer overrides prior initialization',
        'patterns':[r".*: warning: initializer overrides prior initialization of this subobject"] },
    { 'category':'logtags',   'severity':severity.LOW, 'option':'self-assign',
        'description':'Assigning value to self',
        'patterns':[r".*: warning: explicitly assigning value of .+ to itself"] },
    { 'category':'logtags',   'severity':severity.LOW, 'option':'gnu-variable-sized-type-not-at-end',
        'description':'GNU extension, variable sized type not at end',
        'patterns':[r".*: warning: field '.+' with variable sized type '.+' not at the end of a struct or class"] },
    { 'category':'logtags',   'severity':severity.LOW, 'option':'tautological-constant-out-of-range-compare',
        'description':'Comparison of constant is always false/true',
        'patterns':[r".*: comparison of .+ is always .+Wtautological-constant-out-of-range-compare"] },
    { 'category':'logtags',   'severity':severity.LOW, 'option':'overloaded-virtual',
        'description':'Hides overloaded virtual function',
        'patterns':[r".*: '.+' hides overloaded virtual function"] },
    { 'category':'logtags',   'severity':severity.LOW, 'option':'incompatible-pointer-types',
        'description':'Incompatible pointer types',
        'patterns':[r".*: warning: incompatible pointer types .+Wincompatible-pointer-types"] },
    { 'category':'logtags',   'severity':severity.LOW, 'option':'asm-operand-widths',
        'description':'ASM value size does not match register size',
        'patterns':[r".*: warning: value size does not match register size specified by the constraint and modifier"] },
    { 'category':'C/C++',   'severity':severity.LOW, 'option':'tautological-compare',
        'description':'Comparison of self is always false',
        'patterns':[r".*: self-comparison always evaluates to false"] },
    { 'category':'C/C++',   'severity':severity.LOW, 'option':'constant-logical-operand',
        'description':'Logical op with constant operand',
        'patterns':[r".*: use of logical '.+' with constant operand"] },
    { 'category':'C/C++',   'severity':severity.LOW, 'option':'literal-suffix',
        'description':'Needs a space between literal and string macro',
        'patterns':[r".*: warning: invalid suffix on literal.+ requires a space .+Wliteral-suffix"] },
    { 'category':'C/C++',   'severity':severity.LOW, 'option':'#warnings',
        'description':'Warnings from #warning',
        'patterns':[r".*: warning: .+-W#warnings"] },
    { 'category':'C/C++',   'severity':severity.LOW, 'option':'absolute-value',
        'description':'Using float/int absolute value function with int/float argument',
        'patterns':[r".*: warning: using .+ absolute value function .+ when argument is .+ type .+Wabsolute-value",
                    r".*: warning: absolute value function '.+' given .+ which may cause truncation .+Wabsolute-value"] },
    { 'category':'C/C++',   'severity':severity.LOW, 'option':'-Wc++11-extensions',
        'description':'Using C++11 extensions',
        'patterns':[r".*: warning: 'auto' type specifier is a C\+\+11 extension"] },
    { 'category':'C/C++',   'severity':severity.LOW,
        'description':'Refers to implicitly defined namespace',
        'patterns':[r".*: warning: using directive refers to implicitly-defined namespace .+"] },
    { 'category':'C/C++',   'severity':severity.LOW, 'option':'-Winvalid-pp-token',
        'description':'Invalid pp token',
        'patterns':[r".*: warning: missing .+Winvalid-pp-token"] },

    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Operator new returns NULL',
        'patterns':[r".*: warning: 'operator new' must not return NULL unless it is declared 'throw\(\)' .+"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wnull-arithmetic',
        'description':'NULL used in arithmetic',
        'patterns':[r".*: warning: NULL used in arithmetic",
                    r".*: warning: comparison between NULL and non-pointer"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'header-guard',
        'description':'Misspelled header guard',
        'patterns':[r".*: warning: '.+' is used as a header guard .+ followed by .+ different macro"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'empty-body',
        'description':'Empty loop body',
        'patterns':[r".*: warning: .+ loop has empty body"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'enum-conversion',
        'description':'Implicit conversion from enumeration type',
        'patterns':[r".*: warning: implicit conversion from enumeration type '.+'"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'switch',
        'description':'case value not in enumerated type',
        'patterns':[r".*: warning: case value not in enumerated type '.+'"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Undefined result',
        'patterns':[r".*: warning: The result of .+ is undefined",
                    r".*: warning: passing an object that .+ has undefined behavior \[-Wvarargs\]",
                    r".*: warning: 'this' pointer cannot be null in well-defined C\+\+ code;",
                    r".*: warning: shifting a negative signed value is undefined"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Division by zero',
        'patterns':[r".*: warning: Division by zero"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Use of deprecated method',
        'patterns':[r".*: warning: '.+' is deprecated .+"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Use of garbage or uninitialized value',
        'patterns':[r".*: warning: .+ is a garbage value",
                    r".*: warning: Function call argument is an uninitialized value",
                    r".*: warning: Undefined or garbage value returned to caller",
                    r".*: warning: Called .+ pointer is.+uninitialized",
                    r".*: warning: Called .+ pointer is.+uninitalized",  # match a typo in compiler message
                    r".*: warning: Use of zero-allocated memory",
                    r".*: warning: Dereference of undefined pointer value",
                    r".*: warning: Passed-by-value .+ contains uninitialized data",
                    r".*: warning: Branch condition evaluates to a garbage value",
                    r".*: warning: The .+ of .+ is an uninitialized value.",
                    r".*: warning: .+ is used uninitialized whenever .+sometimes-uninitialized",
                    r".*: warning: Assigned value is garbage or undefined"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Result of malloc type incompatible with sizeof operand type',
        'patterns':[r".*: warning: Result of '.+' is converted to .+ incompatible with sizeof operand type"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wsizeof-array-argument',
        'description':'Sizeof on array argument',
        'patterns':[r".*: warning: sizeof on array function parameter will return"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wsizeof-pointer-memacces',
        'description':'Bad argument size of memory access functions',
        'patterns':[r".*: warning: .+\[-Wsizeof-pointer-memaccess\]"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Return value not checked',
        'patterns':[r".*: warning: The return value from .+ is not checked"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Possible heap pollution',
        'patterns':[r".*: warning: .*Possible heap pollution from .+ type .+"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Allocation size of 0 byte',
        'patterns':[r".*: warning: Call to .+ has an allocation size of 0 byte"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Result of malloc type incompatible with sizeof operand type',
        'patterns':[r".*: warning: Result of '.+' is converted to .+ incompatible with sizeof operand type"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wfor-loop-analysis',
        'description':'Variable used in loop condition not modified in loop body',
        'patterns':[r".*: warning: variable '.+' used in loop condition.*Wfor-loop-analysis"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM,
        'description':'Closing a previously closed file',
        'patterns':[r".*: warning: Closing a previously closed file"] },
    { 'category':'C/C++',   'severity':severity.MEDIUM, 'option':'-Wunnamed-type-template-args',
        'description':'Unnamed template type argument',
        'patterns':[r".*: warning: template argument.+Wunnamed-type-template-args"] },

    { 'category':'C/C++',   'severity':severity.HARMLESS,
        'description':'Discarded qualifier from pointer target type',
        'patterns':[r".*: warning: .+ discards '.+' qualifier from pointer target type"] },
    { 'category':'C/C++',   'severity':severity.HARMLESS,
        'description':'Use snprintf instead of sprintf',
        'patterns':[r".*: warning: .*sprintf is often misused; please use snprintf"] },
    { 'category':'C/C++',   'severity':severity.HARMLESS,
        'description':'Unsupported optimizaton flag',
        'patterns':[r".*: warning: optimization flag '.+' is not supported"] },
    { 'category':'C/C++',   'severity':severity.HARMLESS,
        'description':'Extra or missing parentheses',
        'patterns':[r".*: warning: equality comparison with extraneous parentheses",
                    r".*: warning: .+ within .+Wlogical-op-parentheses"] },
    { 'category':'C/C++',   'severity':severity.HARMLESS, 'option':'mismatched-tags',
        'description':'Mismatched class vs struct tags',
        'patterns':[r".*: warning: '.+' defined as a .+ here but previously declared as a .+mismatched-tags",
                    r".*: warning: .+ was previously declared as a .+mismatched-tags"] },

    # these next ones are to deal with formatting problems resulting from the log being mixed up by 'make -j'
    { 'category':'C/C++',   'severity':severity.SKIP,
        'description':'',
        'patterns':[r".*: warning: ,$"] },
    { 'category':'C/C++',   'severity':severity.SKIP,
        'description':'',
        'patterns':[r".*: warning: $"] },
    { 'category':'C/C++',   'severity':severity.SKIP,
        'description':'',
        'patterns':[r".*: warning: In file included from .+,"] },

    # warnings from clang-tidy
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy readability',
        'patterns':[r".*: .+\[readability-.+\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy c++ core guidelines',
        'patterns':[r".*: .+\[cppcoreguidelines-.+\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy google-default-arguments',
        'patterns':[r".*: .+\[google-default-arguments\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy google-runtime-int',
        'patterns':[r".*: .+\[google-runtime-int\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy google-runtime-operator',
        'patterns':[r".*: .+\[google-runtime-operator\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy google-runtime-references',
        'patterns':[r".*: .+\[google-runtime-references\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy google-build',
        'patterns':[r".*: .+\[google-build-.+\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy google-explicit',
        'patterns':[r".*: .+\[google-explicit-.+\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy google-readability',
        'patterns':[r".*: .+\[google-readability-.+\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy google-global',
        'patterns':[r".*: .+\[google-global-.+\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy google- other',
        'patterns':[r".*: .+\[google-.+\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy modernize',
        'patterns':[r".*: .+\[modernize-.+\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy misc',
        'patterns':[r".*: .+\[misc-.+\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy performance-faster-string-find',
        'patterns':[r".*: .+\[performance-faster-string-find\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy performance-for-range-copy',
        'patterns':[r".*: .+\[performance-for-range-copy\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy performance-implicit-cast-in-loop',
        'patterns':[r".*: .+\[performance-implicit-cast-in-loop\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy performance-unnecessary-copy-initialization',
        'patterns':[r".*: .+\[performance-unnecessary-copy-initialization\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy performance-unnecessary-value-param',
        'patterns':[r".*: .+\[performance-unnecessary-value-param\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-analyzer Unreachable code',
        'patterns':[r".*: warning: This statement is never executed.*UnreachableCode"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-analyzer Size of malloc may overflow',
        'patterns':[r".*: warning: .* size of .* may overflow .*MallocOverflow"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-analyzer Stream pointer might be NULL',
        'patterns':[r".*: warning: Stream pointer might be NULL .*unix.Stream"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-analyzer Opened file never closed',
        'patterns':[r".*: warning: Opened File never closed.*unix.Stream"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-analyzer sozeof() on a pointer type',
        'patterns':[r".*: warning: .*calls sizeof.* on a pointer type.*SizeofPtr"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-analyzer Pointer arithmetic on non-array variables',
        'patterns':[r".*: warning: Pointer arithmetic on non-array variables .*PointerArithm"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-analyzer Subtraction of pointers of different memory chunks',
        'patterns':[r".*: warning: Subtraction of two pointers .*PointerSub"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-analyzer Access out-of-bound array element',
        'patterns':[r".*: warning: Access out-of-bound array element .*ArrayBound"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-analyzer Out of bound memory access',
        'patterns':[r".*: warning: Out of bound memory access .*ArrayBoundV2"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-analyzer Possible lock order reversal',
        'patterns':[r".*: warning: .* Possible lock order reversal.*PthreadLock"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-analyzer Argument is a pointer to uninitialized value',
        'patterns':[r".*: warning: .* argument is a pointer to uninitialized value .*CallAndMessage"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-analyzer cast to struct',
        'patterns':[r".*: warning: Casting a non-structure type to a structure type .*CastToStruct"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-analyzer call path problems',
        'patterns':[r".*: warning: Call Path : .+"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-analyzer other',
        'patterns':[r".*: .+\[clang-analyzer-.+\]$",
                    r".*: Call Path : .+$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy CERT',
        'patterns':[r".*: .+\[cert-.+\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-tidy llvm',
        'patterns':[r".*: .+\[llvm-.+\]$"] },
    { 'category':'C/C++',   'severity':severity.TIDY,
        'description':'clang-diagnostic',
        'patterns':[r".*: .+\[clang-diagnostic-.+\]$"] },

    # catch-all for warnings this script doesn't know about yet
    { 'category':'C/C++',   'severity':severity.UNKNOWN,
        'description':'Unclassified/unrecognized warnings',
        'patterns':[r".*: warning: .+"] },
]

for w in warnpatterns:
    w['members'] = []
    if 'option' not in w:
        w['option'] = ''

# A list of [project_name, file_path_pattern].
# project_name should not contain comma, to be used in CSV output.
projectlist = [
    ['art',                 r"(^|.*/)art/.*: warning:"],
    ['bionic',              r"(^|.*/)bionic/.*: warning:"],
    ['bootable',            r"(^|.*/)bootable/.*: warning:"],
    ['build',               r"(^|.*/)build/.*: warning:"],
    ['cts',                 r"(^|.*/)cts/.*: warning:"],
    ['dalvik',              r"(^|.*/)dalvik/.*: warning:"],
    ['developers',          r"(^|.*/)developers/.*: warning:"],
    ['development',         r"(^|.*/)development/.*: warning:"],
    ['device',              r"(^|.*/)device/.*: warning:"],
    ['doc',                 r"(^|.*/)doc/.*: warning:"],
    # match external/google* before external/
    ['external/google',     r"(^|.*/)external/google.*: warning:"],
    ['external/non-google', r"(^|.*/)external/.*: warning:"],
    ['frameworks',          r"(^|.*/)frameworks/.*: warning:"],
    ['hardware',            r"(^|.*/)hardware/.*: warning:"],
    ['kernel',              r"(^|.*/)kernel/.*: warning:"],
    ['libcore',             r"(^|.*/)libcore/.*: warning:"],
    ['libnativehelper',      r"(^|.*/)libnativehelper/.*: warning:"],
    ['ndk',                 r"(^|.*/)ndk/.*: warning:"],
    ['packages',            r"(^|.*/)packages/.*: warning:"],
    ['pdk',                 r"(^|.*/)pdk/.*: warning:"],
    ['prebuilts',           r"(^|.*/)prebuilts/.*: warning:"],
    ['system',              r"(^|.*/)system/.*: warning:"],
    ['toolchain',           r"(^|.*/)toolchain/.*: warning:"],
    ['test',                r"(^|.*/)test/.*: warning:"],
    ['tools',               r"(^|.*/)tools/.*: warning:"],
    # match vendor/google* before vendor/
    ['vendor/google',       r"(^|.*/)vendor/google.*: warning:"],
    ['vendor/non-google',   r"(^|.*/)vendor/.*: warning:"],
    # keep out/obj and other patterns at the end.
    ['out/obj', r".*/(gen|obj[^/]*)/(include|EXECUTABLES|SHARED_LIBRARIES|STATIC_LIBRARIES)/.*: warning:"],
    ['other',   r".*: warning:"],
]

projectpatterns = []
for p in projectlist:
    projectpatterns.append({'description':p[0], 'members':[], 'pattern':re.compile(p[1])})

projectnames = [p[0] for p in projectlist]

# Each warning pattern has 3 dictionaries:
# (1) 'projects' maps a project name to number of warnings in that project.
# (2) 'projectanchor' maps a project name to its anchor number for HTML.
# (3) 'projectwarning' maps a project name to a list of warning of that project.
for w in warnpatterns:
    w['projects'] = {}
    w['projectanchor'] = {}
    w['projectwarning'] = {}

platformversion = 'unknown'
targetproduct = 'unknown'
targetvariant = 'unknown'


##### Data and functions to dump html file. ##################################

anchor = 0
cur_row_class = 0

html_script_style = """\
    <script type="text/javascript">
    function expand(id) {
      var e = document.getElementById(id);
      var f = document.getElementById(id + "_mark");
      if (e.style.display == 'block') {
         e.style.display = 'none';
         f.innerHTML = '&#x2295';
      }
      else {
         e.style.display = 'block';
         f.innerHTML = '&#x2296';
      }
    };
    function expand_collapse(show) {
      for (var id = 1; ; id++) {
        var e = document.getElementById(id + "");
        var f = document.getElementById(id + "_mark");
        if (!e || !f) break;
        e.style.display = (show ? 'block' : 'none');
        f.innerHTML = (show ? '&#x2296' : '&#x2295');
      }
    };
    </script>
    <style type="text/css">
    th,td{border-collapse:collapse; border:1px solid black;}
    .button{color:blue;font-size:110%;font-weight:bolder;}
    .bt{color:black;background-color:transparent;border:none;outline:none;
        font-size:140%;font-weight:bolder;}
    .c0{background-color:#e0e0e0;}
    .c1{background-color:#d0d0d0;}
    .t1{border-collapse:collapse; width:100%; border:1px solid black;}
    </style>\n"""


def output(text):
    print text,

def htmlbig(param):
    return '<font size="+2">' + param + '</font>'

def dumphtmlprologue(title):
    output('<html>\n<head>\n')
    output('<title>' + title + '</title>\n')
    output(html_script_style)
    output('</head>\n<body>\n')
    output(htmlbig(title))
    output('<p>\n')

def dumphtmlepilogue():
    output('</body>\n</head>\n</html>\n')

def tablerow(text):
    global cur_row_class
    cur_row_class = 1 - cur_row_class
    # remove last '\n'
    t = text[:-1] if text[-1] == '\n' else text
    output('<tr><td class="c' + str(cur_row_class) + '">' + t + '</td></tr>\n')

def sortwarnings():
    for i in warnpatterns:
        i['members'] = sorted(set(i['members']))

# dump a table of warnings per project and severity
def dumpstatsbyproject():
    projects = set(projectnames)
    severities = set(severity.kinds)

    # warnings[p][s] is number of warnings in project p of severity s.
    warnings = {p:{s:0 for s in severity.kinds} for p in projectnames}
    for i in warnpatterns:
        s = i['severity']
        for p in i['projects']:
            warnings[p][s] += i['projects'][p]

    # totalbyproject[p] is number of warnings in project p.
    totalbyproject = {p:sum(warnings[p][s] for s in severity.kinds)
                      for p in projectnames}

    # totalbyseverity[s] is number of warnings of severity s.
    totalbyseverity = {s:sum(warnings[p][s] for p in projectnames)
                       for s in severity.kinds}

    # emit table header
    output('<blockquote><table border=1>\n<tr><th>Project</th>\n')
    for s in severity.kinds:
        if totalbyseverity[s]:
            output('<th width="8%"><span style="background-color:{}">{}</span></th>'.
                   format(severity.color[s], severity.columnheader[s]))
    output('<th>TOTAL</th></tr>\n')

    # emit a row of warning counts per project, skip no-warning projects
    totalallprojects = 0
    for p in projectnames:
        if totalbyproject[p]:
            output('<tr><td align="left">{}</td>'.format(p))
            for s in severity.kinds:
                if totalbyseverity[s]:
                    output('<td align="right">{}</td>'.format(warnings[p][s]))
            output('<td align="right">{}</td>'.format(totalbyproject[p]))
            totalallprojects += totalbyproject[p]
            output('</tr>\n')

    # emit a row of warning counts per severity
    totalallseverities = 0
    output('<tr><td align="right">TOTAL</td>')
    for s in severity.kinds:
        if totalbyseverity[s]:
            output('<td align="right">{}</td>'.format(totalbyseverity[s]))
            totalallseverities += totalbyseverity[s]
    output('<td align="right">{}</td></tr>\n'.format(totalallprojects))

    # at the end of table, verify total counts
    output('</table></blockquote><br>\n')
    if totalallprojects != totalallseverities:
        output('<h3>ERROR: Sum of warnings by project ' +
               '!= Sum of warnings by severity.</h3>\n')

# dump some stats about total number of warnings and such
def dumpstats():
    known = 0
    skipped = 0
    unknown = 0
    sortwarnings()
    for i in warnpatterns:
        if i['severity'] == severity.UNKNOWN:
            unknown += len(i['members'])
        elif i['severity'] == severity.SKIP:
            skipped += len(i['members'])
        else:
            known += len(i['members'])
    output('\nNumber of classified warnings: <b>' + str(known) + '</b><br>' )
    output('\nNumber of skipped warnings: <b>' + str(skipped) + '</b><br>')
    output('\nNumber of unclassified warnings: <b>' + str(unknown) + '</b><br>')
    total = unknown + known + skipped
    output('\nTotal number of warnings: <b>' + str(total) + '</b>')
    if total < 1000:
        output('(low count may indicate incremental build)')
    output('<br><br>\n')

def emitbuttons():
    output('<button class="button" onclick="expand_collapse(1);">' +
           'Expand all warnings</button>\n' +
           '<button class="button" onclick="expand_collapse(0);">' +
           'Collapse all warnings</button><br>\n')

# dump everything for a given severity
def dumpseverity(sev):
    global anchor
    total = 0
    for i in warnpatterns:
        if i['severity'] == sev:
            total = total + len(i['members'])
    output('\n<br><span style="background-color:' + severity.color[sev] + '"><b>' +
           severity.header[sev] + ': ' + str(total) + '</b></span>\n')
    output('<blockquote>\n')
    for i in warnpatterns:
        if i['severity'] == sev and len(i['members']) > 0:
            anchor += 1
            i['anchor'] = str(anchor)
            if args.byproject:
                dumpcategorybyproject(sev, i)
            else:
                dumpcategory(sev, i)
    output('</blockquote>\n')

# emit all skipped project anchors for expand_collapse.
def dumpskippedanchors():
    output('<div style="display:none;">\n')  # hide these fake elements
    for i in warnpatterns:
        if i['severity'] == severity.SKIP and len(i['members']) > 0:
            projects = i['projectwarning'].keys()
            for p in projects:
                output('<div id="' + i['projectanchor'][p] + '"></div>' +
                       '<div id="' + i['projectanchor'][p] + '_mark"></div>\n')
    output('</div>\n')

def allpatterns(cat):
    pats = ''
    for i in cat['patterns']:
        pats += i
        pats += ' / '
    return pats

def descriptionfor(cat):
    if cat['description'] != '':
        return cat['description']
    return allpatterns(cat)


# show which warnings no longer occur
def dumpfixed():
    global anchor
    anchor += 1
    mark = str(anchor) + '_mark'
    output('\n<br><p style="background-color:lightblue"><b>' +
           '<button id="' + mark + '" ' +
           'class="bt" onclick="expand(' + str(anchor) + ');">' +
           '&#x2295</button> Fixed warnings. ' +
           'No more occurences. Please consider turning these into ' +
           'errors if possible, before they are reintroduced in to the build' +
           ':</b></p>\n')
    output('<blockquote>\n')
    fixed_patterns = []
    for i in warnpatterns:
        if len(i['members']) == 0:
            fixed_patterns.append(i['description'] + ' (' +
                                  allpatterns(i) + ')')
        if i['option']:
            fixed_patterns.append(' ' + i['option'])
    fixed_patterns.sort()
    output('<div id="' + str(anchor) + '" style="display:none;"><table>\n')
    for i in fixed_patterns:
        tablerow(i)
    output('</table></div>\n')
    output('</blockquote>\n')

def warningwithurl(line):
    if not args.url:
        return line
    m = re.search( r'^([^ :]+):(\d+):(.+)', line, re.M|re.I)
    if not m:
        return line
    filepath = m.group(1)
    linenumber = m.group(2)
    warning = m.group(3)
    if args.separator:
        return '<a href="' + args.url + '/' + filepath + args.separator + linenumber + '">' + filepath + ':' + linenumber + '</a>:' + warning
    else:
        return '<a href="' + args.url + '/' + filepath + '">' + filepath + '</a>:' + linenumber + ':' + warning

def dumpgroup(sev, anchor, description, warnings):
    mark = anchor + '_mark'
    output('\n<table class="t1">\n')
    output('<tr bgcolor="' + severity.color[sev] + '">' +
           '<td><button class="bt" id="' + mark +
           '" onclick="expand(\'' + anchor + '\');">' +
           '&#x2295</button> ' + description + '</td></tr>\n')
    output('</table>\n')
    output('<div id="' + anchor + '" style="display:none;">')
    output('<table class="t1">\n')
    for i in warnings:
        tablerow(warningwithurl(i))
    output('</table></div>\n')

# dump warnings in a category
def dumpcategory(sev, cat):
    description = descriptionfor(cat) + ' (' + str(len(cat['members'])) + ')'
    dumpgroup(sev, cat['anchor'], description, cat['members'])

# similar to dumpcategory but output one table per project.
def dumpcategorybyproject(sev, cat):
    warning = descriptionfor(cat)
    projects = cat['projectwarning'].keys()
    projects.sort()
    for p in projects:
        anchor = cat['projectanchor'][p]
        projectwarnings = cat['projectwarning'][p]
        description = '{}, in {} ({})'.format(warning, p, len(projectwarnings))
        dumpgroup(sev, anchor, description, projectwarnings)

def findproject(line):
    for p in projectpatterns:
        if p['pattern'].match(line):
            return p['description']
    return '???'

def classifywarning(line):
    global anchor
    for i in warnpatterns:
        for cpat in i['compiledpatterns']:
            if cpat.match(line):
                i['members'].append(line)
                pname = findproject(line)
                # Count warnings by project.
                if pname in i['projects']:
                    i['projects'][pname] += 1
                else:
                    i['projects'][pname] = 1
                # Collect warnings by project.
                if args.byproject:
                    if pname in i['projectwarning']:
                        i['projectwarning'][pname].append(line)
                    else:
                        i['projectwarning'][pname] = [line]
                    if pname not in i['projectanchor']:
                        anchor += 1
                        i['projectanchor'][pname] = str(anchor)
                return
            else:
                # If we end up here, there was a problem parsing the log
                # probably caused by 'make -j' mixing the output from
                # 2 or more concurrent compiles
                pass

# precompiling every pattern speeds up parsing by about 30x
def compilepatterns():
    for i in warnpatterns:
        i['compiledpatterns'] = []
        for pat in i['patterns']:
            i['compiledpatterns'].append(re.compile(pat))

def parseinputfile():
    global platformversion
    global targetproduct
    global targetvariant
    infile = open(args.buildlog, 'r')
    linecounter = 0

    warningpattern = re.compile('.* warning:.*')
    compilepatterns()

    # read the log file and classify all the warnings
    warninglines = set()
    for line in infile:
        # replace fancy quotes with plain ol' quotes
        line = line.replace("‘", "'");
        line = line.replace("’", "'");
        if warningpattern.match(line):
            if line not in warninglines:
                classifywarning(line)
                warninglines.add(line)
        else:
            # save a little bit of time by only doing this for the first few lines
            if linecounter < 50:
                linecounter +=1
                m = re.search('(?<=^PLATFORM_VERSION=).*', line)
                if m != None:
                    platformversion = m.group(0)
                m = re.search('(?<=^TARGET_PRODUCT=).*', line)
                if m != None:
                    targetproduct = m.group(0)
                m = re.search('(?<=^TARGET_BUILD_VARIANT=).*', line)
                if m != None:
                    targetvariant = m.group(0)


# dump the html output to stdout
def dumphtml():
    dumphtmlprologue('Warnings for ' + platformversion + ' - ' + targetproduct + ' - ' + targetvariant)
    dumpstats()
    dumpstatsbyproject()
    emitbuttons()
    # sort table based on number of members once dumpstats has deduplicated the
    # members.
    warnpatterns.sort(reverse=True, key=lambda i: len(i['members']))
    # Dump warnings by severity. If severity.SKIP warnings are not dumpped,
    # the project anchors should be dumped through dumpskippedanchors.
    for s in severity.kinds:
        dumpseverity(s)
    dumpfixed()
    dumphtmlepilogue()


##### Functions to count warnings and dump csv file. #########################

def descriptionforcsv(cat):
    if cat['description'] == '':
        return '?'
    return cat['description']

def stringforcsv(s):
    if ',' in s:
        return '"{}"'.format(s)
    return s

def countseverity(sev, kind):
  sum = 0
  for i in warnpatterns:
      if i['severity'] == sev and len(i['members']) > 0:
          n = len(i['members'])
          sum += n
          warning = stringforcsv(kind + ': ' + descriptionforcsv(i))
          print '{},,{}'.format(n, warning)
          # print number of warnings for each project, ordered by project name.
          projects = i['projects'].keys()
          projects.sort()
          for p in projects:
              print '{},{},{}'.format(i['projects'][p], p, warning)
  print '{},,{}'.format(sum, kind + ' warnings')
  return sum

# dump number of warnings in csv format to stdout
def dumpcsv():
    sortwarnings()
    total = 0
    for s in severity.kinds:
        total += countseverity(s, severity.columnheader[s])
    print '{},,{}'.format(total, 'All warnings')


parseinputfile()
if args.gencsv:
    dumpcsv()
else:
    dumphtml()
